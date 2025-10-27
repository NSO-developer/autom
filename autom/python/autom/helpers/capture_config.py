# -*- mode: python; python-indent: 4 -*-
"""
Autom capture_config
"""
from asyncio.log import logger
from datetime import datetime
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict, Any
import difflib
import os
import operator
import re
import json
import socket
import xml.etree.ElementTree as ET
import time
import shutil


import _ncs
from _ncs import maapi
import ncs
from ncs import maagic
from ncs.dp import Action
from .robot_generator import RobotService

# Constants for timing and configuration
MAX_PLAN_WAIT_TIME = 100
PLAN_SLEEP_TIME = 1
MAX_SERVICE_READY_WAIT_TIME = 300
SERVICE_READY_SLEEP_TIME = 1

# Configuration type constants
CONFIG_TYPES_AFTER = ['service_config_xml', 'cli', 'xml']
CONFIG_TYPES_BEFORE = ['cli', 'xml']
CONFIG_TYPES_ISOLATION = ['xml']

# Error messages
ISOLATION_ERROR_MSG = "The option test-in-isolation doesn't work with only child services as input"

# Parameter classes for better organization
@dataclass
class CaptureConfigParams:
    """Configuration parameters for capture operation"""
    service_keypath: str
    current_date_time: str
    no_networking: bool = False
    test_in_isolation: bool = False
    include_children: bool = False
    use_date_time: bool = False
    no_dry_run_data: bool = False
    service_config_modify_file: Optional[str] = None

@dataclass
class ServiceGroups:
    """Groups of services by type"""
    parent_services: List[str]
    regular_services: List[str]
    child_services: List[str]
    top_level_services: List[str]
    services_list: List[str]
    services_xpath: str

# Utility functions
def should_test_in_isolation(test_in_isolation: Any) -> bool:
    """Check if test should be run in isolation mode"""
    return "True" in str(test_in_isolation)

def should_skip_dry_run_data(no_dry_run_data: bool) -> bool:
    """Check if dry run data should be skipped"""
    return no_dry_run_data is True
def should_use_test(packages_folder_path: str) -> bool:
    """Determine if test folder should be used based on folder path"""
    if "packages" in packages_folder_path.lower():
        return True
    return False

def get_devices_from_keypaths(trans: Any, kp_input: str) -> List[str]:
    """Extract devices from keypath input"""
    devices = []
    keypath_node = ncs.maagic.get_node(trans, kp_input)
    devices_path = keypath_node._path + "/modified/devices"
    devices += ncs.maagic.get_node(trans, devices_path).as_list()
    return devices

def capture_device_configs_for_phase(logger: Any, devices: List[str], sock_maapi: Any, 
                                   trans: Any, thandle: Any, output_folder: str, 
                                   phase: str, no_networking: bool) -> Dict[str, str]:
    """Capture device configurations for a specific phase"""
    device_configs = {}
    for device in devices:
        config_file = device_config_capture(logger, sock_maapi, trans, thandle, device,
                                           output_folder, phase=phase, no_networking=no_networking)
        device_configs[device] = config_file
    return device_configs

def write_device_diffs(devices: List[str], output_folder: str) -> None:
    """
    Write diff files for all devices comparing before and after configurations
    
    This function should only be called after both 'before' and 'after' configurations
    have been captured, as it compares the two states.
    """
    for device in devices:
        dev_config_before_file_cli = os.path.join(output_folder, f"{device}_before.cli")
        dev_config_after_file_cli = os.path.join(output_folder, f"{device}_after.cli")
        device_diff_write(device, output_folder, dev_config_before_file_cli, dev_config_after_file_cli)

def load_merge_files(sock_maapi: Any, files_to_load_merge: List[str], 
                    no_networking: bool, uinfo: Any) -> None:
    """Load merge files if provided"""
    for file in files_to_load_merge:
        load_cdb_config_from_file(sock_maapi, file, no_networking, uinfo)

def process_plan_for_service(logger: Any, kp_node_path: str, services_xpath: str, 
                           uinfo: Any) -> Tuple[bool, Optional[str], Any, Optional[str]]:
    """Process plan-related operations for a service"""
    xpath_node = find_xpath_for_keypath(logger, kp_node_path, services_xpath)
    plan_exists, plan_location = service_has_plan(logger, kp_node_path, xpath_node, uinfo)
    plan_xpath = None
    if plan_exists is not False:
        plan_xpath = xpath(plan_location)
    return plan_exists, plan_location, xpath_node, plan_xpath

def wait_for_plan_if_exists(logger: Any, plan_exists: bool, plan_location: Optional[str], 
                          xpath_node: Any, root: Any, trans: Any) -> None:
    """Handle plan waiting logic"""
    if plan_exists is not False:
        wait_for_zombie(logger, MAX_PLAN_WAIT_TIME, PLAN_SLEEP_TIME, 
                       root, trans, plan_location, xpath_node)

def delete_services_from_cdb(logger: Any, trans: Any, kp_input: str, 
                           services_xpath: str, sock_maapi: Any, uinfo: Any, 
                           no_networking: bool, root: Any) -> None:
    """Delete service instances from CDB and wait for plans"""
    kp_node = ncs.maagic.get_node(trans, kp_input)
    plan_exists, plan_location, xpath_node, plan_xpath = process_plan_for_service(
                           logger, kp_node._path, services_xpath, uinfo)
        
    delete_kpath_from_cdb(sock_maapi, kp_node, no_networking, uinfo)
    wait_for_plan_if_exists(logger, plan_exists, plan_location, xpath_node, root, trans)

def redeploy_services(trans: Any, kp_input: str, devices: List[str], 
                     no_networking: bool, root: Any) -> None:
    """Redeploy services with reconcile"""
    kp_node = ncs.maagic.get_node(trans, kp_input)
    redeploy_input = kp_node.re_deploy.get_input()
    redeploy_input.reconcile.create()
        
    if no_networking:
        redeploy_input.no_networking.create()
        kp_node.re_deploy(redeploy_input)
        for device in devices:
            root.ncs__devices.ncs__device[device].compare_config()
    else:
        kp_node.re_deploy(redeploy_input)

def redeploy_services_to_remove(trans: Any, services_keypaths_to_remove: List[str], 
                               no_networking: bool, root: Any) -> None:
    """Redeploy services that were marked for removal"""
    for path in services_keypaths_to_remove:
        path_node = ncs.maagic.get_node(trans, path)
        redeploy_input = path_node.re_deploy.get_input()
        redeploy_input.reconcile.create()
        path_node.re_deploy(redeploy_input)
        
        if no_networking:
            devices_path_mod = path_node._path + "/modified/devices"
            devices_list = ncs.maagic.get_node(trans, devices_path_mod).as_list()
            for device_name in devices_list:
                root.ncs__devices.ncs__device[device_name].compare_config()

def handle_test_isolation_workflow(logger: Any, keypath_node: Any, 
                                 services_keypaths_to_remove: List[str],
                                 services_xpath: str, sock_maapi: Any, thandle: Any, 
                                 files: Any, kp_input: List[str], uinfo: Any, 
                                 no_networking: bool, trans: Any, root: Any) -> bool:
    """
    Handle test-in-isolation workflow
    
    Returns:
        bool: True if successful, False if isolation cannot be performed
    """
    # Step 1: Capture configuration for full backup
    cdb_config_capture(logger, sock_maapi, thandle, files.output_folder,
                      phase='before_test_in_isolation', 
                      config_types=CONFIG_TYPES_ISOLATION,
                      kp_list=kp_input, index=0)

    # Step 2: Remove other service instances if applicable
    if (len(services_keypaths_to_remove) > 0 and 
        keypath_node._path in services_keypaths_to_remove):
        services_keypaths_to_remove.remove(keypath_node._path)
        
        for path in services_keypaths_to_remove:
            path_node = ncs.maagic.get_node(trans, path)
            plan_exists, plan_location, xpath_node, plan_xpath = process_plan_for_service(
                logger, keypath_node._path, services_xpath, uinfo)
                
            delete_kpath_from_cdb(sock_maapi, path_node, no_networking, uinfo)
            logger.info("Path deleted: %s", str(path_node._path))
            wait_for_plan_if_exists(logger, plan_exists, plan_location, xpath_node, root, trans)
        
        return True
    else:
        logger.info("All services could be children, please check input")
        return False

def capture_modifications_for_service(trans: Any, uinfo: Any, kp_input: List[str], 
                                     files: Any) -> None:
    """Extract modification capture logic"""
    capture_modifications_cli(trans, uinfo.username, kp_input,
                             files.get_modifications_file_cli, write_to_file=True)
    capture_modifications(trans, uinfo.username, kp_input,
                         None, files.get_modifications_file_xml, write_to_file=True)

def generate_dry_run_configurations(files: Any, uinfo: Any, logger: Any) -> None:
    """Generate all dry-run configuration files"""
    dryrun_configuration_xml(maapi.CONFIG_XML_PRETTY,
                           files.service_config_file_xml, files.dry_run_xml, uinfo)
    dryrun_configuration_cli(maapi.CONFIG_XML_PRETTY,
                           files.service_config_file_xml, files.dry_run_cli,
                           uinfo, logger)
    dryrun_configuration_native(maapi.CONFIG_XML_PRETTY,
                              files.service_config_file_xml, files.dry_run_native,
                              uinfo, logger)

def get_load_file_for_config(config_params: CaptureConfigParams, files: Any) -> str:
    """Determine which config file to load based on test mode"""
    if should_test_in_isolation(config_params.test_in_isolation):
        return files.config_before_test_in_isolation_file_xml
    elif should_run_modify_workflow(config_params):
        return files.config_before_file_xml
    else:
        return files.config_after_file_xml

def filter_pre_config_devices(pre_config_devices: List[str], 
                             devices_list: List[str]) -> List[str]:
    """Filter pre_config_devices to only include affected devices"""
    filtered_devices = []
    for device in pre_config_devices:
        if device in devices_list:
            filtered_devices.append(device)
    return filtered_devices

def cleanup_isolation_files(config_params: CaptureConfigParams, files: Any) -> None:
    """Clean up temporary files after isolation testing"""
    if should_test_in_isolation(config_params.test_in_isolation):
        os.remove(files.config_before_test_in_isolation_file_xml)

def handle_child_services_redeployment(logger: Any, trans: Any, kp_input: List[str], 
                                     config_params: CaptureConfigParams, 
                                     uinfo: Any, service_groups: ServiceGroups) -> None:
    """Handle child services redeployment if include_children is enabled"""
    if not config_params.include_children:
        return
        
    for kp_node in kp_input:
        kp_node = ncs.maagic.get_node(trans, kp_node)
        path = get_top_level_parent(logger, uinfo, trans, kp_node._path, service_groups.services_list)

        logger.info("Top Level svc Path: %s", path)
        if path is not None:
            k_node = ncs.maagic.get_node(trans, path)
            redeploy_input = k_node.re_deploy.get_input()
            redeploy_input.reconcile.create()
            redeploy_input.no_networking.create()
            k_node.re_deploy(redeploy_input)
            k_node.re_deploy(redeploy_input)  # Deploy twice as in original
            logger.info("Re-deploy reconcile no-networking performed twice on parent: %s", path)

def handle_final_service_readiness_check(logger: Any, trans: Any, kp_input: str, 
                                       service_groups: ServiceGroups, 
                                       uinfo: Any, sock_maapi: Any) -> None:
    """Handle final service readiness check"""
    kp_node = ncs.maagic.get_node(trans, kp_input)
    plan_exists, plan_location, xpath_node, plan_xpath = process_plan_for_service(
            logger, kp_node._path, service_groups.services_xpath, uinfo)
            
    if plan_exists is not False:
        plan_ready = nano_service_ready(logger, uinfo, trans, plan_location, 
                                          sock_maapi, MAX_SERVICE_READY_WAIT_TIME, 
                                          SERVICE_READY_SLEEP_TIME)

def should_run_modify_workflow(config_params: CaptureConfigParams) -> bool:
    """Check if service modification workflow should be executed"""
    return (config_params.service_config_modify_file is not None and 
            config_params.service_config_modify_file != "")

def load_and_apply_service_modification(sock_maapi: Any, modify_file: str, 
                                      no_networking: bool, uinfo: Any) -> None:
    """Load service modification XML and apply it to CDB"""
    maapi, thandle_rw = load_cdb_config_from_file_and_leave_trans_open(sock_maapi, modify_file, no_networking, uinfo)
    return maapi, thandle_rw
def generate_modified_dry_run_configurations(files: Any, uinfo: Any, logger: Any) -> None:
    """Generate dry-run configurations for modified service"""
    # Generate modified dry-run XML
    dryrun_configuration_xml(maapi.CONFIG_XML_PRETTY,
                           files.service_config_modify, files.dry_run_modify_xml,
                           uinfo)
    # Generate modified dry-run CLI
    dryrun_configuration_cli(maapi.CONFIG_XML_PRETTY,
                           files.service_config_modify, files.dry_run_modify_cli,
                           uinfo, logger)

def capture_modify_modifications(trans: Any, uinfo: Any, kp_input: List[str], 
                               files: Any) -> None:
    """Capture modifications for the service modification workflow"""
    # Capture CLI modifications
    capture_modifications_cli(trans, uinfo.username, kp_input,
                             files.get_modifications_modify_file_cli, write_to_file=True)
    # Capture XML modifications  
    capture_modifications(trans, uinfo.username, kp_input,
                         None, files.get_modifications_modify_file_xml, write_to_file=True)

def handle_service_modify_workflow(logger: Any, trans: Any, sock_maapi: Any, 
                                 config_params: CaptureConfigParams, files: Any,
                                 kp_input: List[str], uinfo: Any) -> None:
    """
    Handle the complete service modification workflow
    
    This workflow:
    1. Loads and applies the service modification XML to CDB
    2. Generates new dry-run configurations (CLI and XML) 
    3. Commits the changes
    4. Captures the modifications made (CLI and XML)
    
    Args:
        logger: Logger instance
        trans: Transaction object
        sock_maapi: MAAPI socket
        config_params: Configuration parameters
        files: Files object with paths
        kp_input: Keypath input list
        uinfo: User information
    """
    logger.info("Starting service modification workflow")
    
    # Ensure files object has required attributes
    ensure_modify_workflow_files(files)
    # Step 0: Store original service configuration before modification
    cdb_config_capture(logger,
                        sock_maapi,
                        trans.th,
                        files.output_folder,
                        phase='after',
                        config_types=['service_config_xml'],
                        kp_input=kp_input,
                        index=0)
    # Step 1: Generate dry-run configurations for modified service
    generate_modified_dry_run_configurations(files, uinfo, logger)
    # Step 2: Load service modification XML
    maapi, thandle_rw = load_and_apply_service_modification(sock_maapi, files.service_config_modify,
                                      config_params.no_networking, uinfo)
    logger.info("Applied service modification from: %s", files.service_config_modify)
    logger.info("Generated modified dry-run configurations")
    if config_params.no_networking:
            maapi.apply_trans_flags(
                sock_maapi,
                thandle_rw,
                keepopen=False,
                flags=_ncs.maapi.COMMIT_NCS_NO_NETWORKING)
    else:
        # not no_networking
        maapi.apply_trans(sock_maapi, thandle_rw, False)
    # Step 3: Commit the changes
    logger.info("Committed service modifications")

    # Step 4: Capture the modifications made
    capture_modify_modifications(trans, uinfo, kp_input, files)
    logger.info("Captured modification changes")
    
    
def ensure_modify_workflow_files(files: Any) -> None:
    """
    Ensure the Files object has the necessary file paths for modify workflow
    
    This function should be called before running the modify workflow to ensure
    all required file paths are available in the files object.
    """
    # Check if modify workflow files exist in the files object
    required_attrs = [
        'service_config_modify',
        'dry_run_modify_xml', 
        'dry_run_modify_cli',
        'get_modifications_file_cli',
        'get_modifications_file_xml'
    ]
    
    missing_attrs = []
    for attr in required_attrs:
        if not hasattr(files, attr):
            missing_attrs.append(attr)
    
    if missing_attrs:
        raise AttributeError(f"Files object missing required attributes for modify workflow: {missing_attrs}")
from .xmlns_parser import parse_xmlns, write_xmlns
from .xpath import xpath
from ..helpers.utils import Folders, Trans
from ..helpers.create_helper import (dryrun_configuration_xml, dryrun_configuration_cli, dryrun_configuration_native, load_cdb_config_from_file_and_leave_trans_open,
                            write_dry_run_data, 
                            find_xpath_for_keypath,
                            service_has_plan, nano_service_ready,
                            get_top_level_parent, 
                            cdb_config_capture, device_config_capture,
                            device_diff_write, capture_modifications, capture_modifications_cli,
                            get_pre_config_files,
                            _open_new_trans, delete_kpath_from_cdb,
                            load_cdb_config_from_file, compare_config_devices_affected,
                            wait_for_zombie, get_parent)

def capture_config(logger, uinfo, folder_path: str, packages_folder_path: str, service_keypath: str,
                   current_date_time: str, no_networking: bool,
                   test_in_isolation: bool, include_children: bool, parent_services: List[str],
                   regular_services: List[str], child_services: List[str], top_level_services: List[str],
                   services_list: List[str], services_xpath: str, pre_config_devices: List[str],
                   pre_config_xpaths: List[str], files_to_load_merge: List[str], 
                   use_date_time: bool, no_dry_run_data: bool, 
                   service_config_modify_file: Optional[str] = None) -> Tuple[Any, str, Any]:
    """
    Main capture_config function with improved parameter organization
    
    Captures service configuration, generates diffs, and handles test isolation scenarios.
    This function has been refactored to use parameter objects for better maintainability.
    
    Args:
        logger: Logger instance
        uinfo: User information object
        folder_path: Base folder path for operations
        packages_folder_path: Path to packages folder
        service_keypath: Service keypath to capture
        current_date_time: Current timestamp for file naming
        no_networking: Whether to run without networking
        test_in_isolation: Whether to test in isolation mode
        include_children: Whether to include child services
        parent_services: List of parent service keypaths
        regular_services: List of regular service keypaths
        child_services: List of child service keypaths
        top_level_services: List of top-level service keypaths
        services_list: Complete list of all services
        services_xpath: XPath for services
        pre_config_devices: List of devices for pre-configuration
        pre_config_xpaths: List of XPaths for pre-configuration
        files_to_load_merge: List of files to load and merge
        use_date_time: Whether to use datetime in folder names
        no_dry_run_data: Whether to skip dry-run data generation
        service_config_modify_file: Optional path to XML file for service modification
    
    Returns:
        Tuple containing:
        - result: Boolean True for success or error message for failure
        - service_config_file_xml: Path to the service configuration XML file
        - files: Files object containing all generated file paths
    """
    # Create parameter objects for better organization
    config_params = CaptureConfigParams(
        service_keypath=service_keypath,
        current_date_time=current_date_time,
        no_networking=no_networking,
        test_in_isolation=test_in_isolation,
        include_children=include_children,
        use_date_time=use_date_time,
        no_dry_run_data=no_dry_run_data,
        service_config_modify_file=service_config_modify_file
    )
    
    service_groups = ServiceGroups(
        parent_services=parent_services,
        regular_services=regular_services,
        child_services=child_services,
        top_level_services=top_level_services,
        services_list=services_list,
        services_xpath=services_xpath
    )
    
    # Call the refactored implementation
    return _capture_config_impl(logger, uinfo, folder_path, packages_folder_path,
                               config_params, service_groups, pre_config_devices,
                               pre_config_xpaths, files_to_load_merge)

def _capture_config_impl(logger, uinfo, folder_path: str, packages_folder_path: str,
                        config_params: CaptureConfigParams, service_groups: ServiceGroups,
                        pre_config_devices: List[str], pre_config_xpaths: List[str],
                        files_to_load_merge: List[str]) -> Tuple[Any, str, Any]:
    """
    Refactored implementation using parameter objects for better maintainability
    
    This function orchestrates the complete configuration capture workflow:
    1. Initialize transaction and extract devices
    2. Setup folder structure and capture modifications
    3. Handle test isolation if enabled
    4. Capture before/after configurations
    5. Generate device diffs and dry-run data
    6. Handle service modification workflow (if requested)
    7. Redeploy services and perform readiness checks
    
    Args:
        self: Logger instance
        uinfo: User information object
        folder_path: Base folder path
        packages_folder_path: Path to packages folder
        config_params: Configuration parameters object
        service_groups: Service groups object
        pre_config_devices: List of devices for pre-configuration
        pre_config_xpaths: List of XPaths for pre-configuration
        files_to_load_merge: List of files to load and merge
    
    Returns:
        Tuple containing (result, service_config_file_xml, files)
    """
    # ignorning R0913 too-many-arguments for capture_config
    # pylint: disable = R0913
    trans, thandle, sock_maapi, root = _open_new_trans(uinfo)
    #sock_maapi = trans.maapi.msock
    # Find the keypath node using maagic
    keypath_node = ncs.maagic.get_node(trans, config_params.service_keypath)
    kp_input = keypath_node._path
    devices = get_devices_from_keypaths(trans, kp_input)
    logger.info("Devices: ", str(devices))
    if len(files_to_load_merge) > 0:
        load_merge_files(sock_maapi, files_to_load_merge, config_params.no_networking, uinfo)
    # Creating the Folders object and using create_folder_env to setup the files
    if packages_folder_path is not None:
        use_test = should_use_test(packages_folder_path)
        files = Folders(packages_folder_path, packages_folder_path, keypath_node, kp_input, trans)
    elif folder_path is not None:
        use_test = should_use_test(folder_path)
        files = Folders(folder_path, folder_path, keypath_node, kp_input, trans)
    else:
        return "Either output-path or packages-folder-path must be provided", "", None
    logger.info("service_config_modify_file: ", str(config_params.service_config_modify_file))
    logger.info("config_params.current_date_time: ", config_params.current_date_time)
    logger.info("config_params.use_date_time: ", str(config_params.use_date_time))
    logger.info("use_test: ", str(use_test))
    logger.info("Creating folder environment")
    files.create_folder_env(config_params.service_config_modify_file, config_params.current_date_time, config_params.use_date_time, use_test)
    # service_config_modify, current_date_time, datetime, use_test, kp_input
    output_path = files.test_folder
    plan_exists, plan_location, xpath_node, plan_xpath = process_plan_for_service(
            logger, kp_input, service_groups.services_xpath, uinfo)
    plan_kpath = None
    if plan_exists is not False:
        plan_ready = nano_service_ready(logger, uinfo, trans, plan_location, 
                                          sock_maapi, MAX_SERVICE_READY_WAIT_TIME, 
                                          SERVICE_READY_SLEEP_TIME)
        plan_kpath = _ncs.maapi.xpath2keypath(trans.maapi.msock, trans.th, plan_xpath)
        
    # Capture modifications for the service before any changes  
    capture_modifications_for_service(trans, uinfo, kp_input, files)
    #Capturing pre-config for each xpath and getting pre_config_files dict
    pre_config_files = get_pre_config_files(logger, trans, thandle, sock_maapi,
                                                pre_config_xpaths, files)
    
    services_keypaths_to_remove = service_groups.top_level_services + service_groups.regular_services
    if should_test_in_isolation(config_params.test_in_isolation):
        # Test in isolation flow
        success = handle_test_isolation_workflow(
            logger, keypath_node, services_keypaths_to_remove, service_groups.services_xpath,
            sock_maapi, thandle, files, kp_input, uinfo, config_params.no_networking, trans, root
        )
        
        if not success:
            function_result = ISOLATION_ERROR_MSG
            return function_result, files.service_config_file_xml, files

    if should_run_modify_workflow(config_params):
        handle_service_modify_workflow(logger, trans, sock_maapi, config_params,
                                     files, kp_input, uinfo)
        cdb_config_capture(logger,
                        sock_maapi,
                        thandle,
                        files.output_folder,
                        phase='after',
                        config_types=['cli', 'xml'],
                        kp_input=kp_input,
                        index=0)
    else:
        # Saving configuration of service and CDB
        cdb_config_capture(logger,
                        sock_maapi,
                        thandle,
                        files.output_folder,
                        phase='after',
                        config_types=CONFIG_TYPES_AFTER,
                        kp_input=kp_input,
                        index=0)
    
    capture_device_configs_for_phase(logger, devices, sock_maapi, trans, thandle,
                                   files.output_folder, 'after', config_params.no_networking)
    if should_run_modify_workflow(config_params):
        # Restore original configuration before modification
        load_cdb_config_from_file(sock_maapi, files.service_config_file_xml, config_params.no_networking, uinfo)
        logger.info("Restored original configuration before modification from: %s", files.service_config_file_xml)
    else:
        # Deleting service from CDB, applying transaction
        delete_services_from_cdb(logger, trans, kp_input, service_groups.services_xpath, sock_maapi, uinfo, config_params.no_networking, root)
    

    cdb_config_capture(logger,
                        sock_maapi,
                        thandle,
                        files.output_folder,
                        phase='before',
                        config_types=CONFIG_TYPES_BEFORE,
                        kp_input=kp_input,
                        index=0)


    # Looping over devices and writing the diff file (comparing before
    #    and after)
    capture_device_configs_for_phase(logger, devices, sock_maapi, trans, thandle,
                                   files.output_folder, 'before', config_params.no_networking)
    
    # Now that we have both before and after configs, generate the diffs
    write_device_diffs(devices, files.output_folder)
    # Generating dry-run configurations
    if should_run_modify_workflow(config_params):
        logger.info("No dry-run created for modify workflow, generating modified dry-run configurations instead")
    else:
        generate_dry_run_configurations(files, uinfo, logger)
    
    # Handle service modification workflow if requested
   
    
    load_file = get_load_file_for_config(config_params, files)
    load_cdb_config_from_file(sock_maapi, load_file, config_params.no_networking, uinfo)
    devices_list = compare_config_devices_affected(trans, kp_input, root)
    filtered_pre_config_devices = filter_pre_config_devices(pre_config_devices, devices_list)
    
    if should_skip_dry_run_data(config_params.no_dry_run_data):
        logger.info("Skipping dry-run data for exec")
    else:
        write_dry_run_data(files.folder_path, kp_input, config_params.test_in_isolation, pre_config_files, filtered_pre_config_devices)
    

    cleanup_isolation_files(config_params, files)
    redeploy_services(trans, kp_input, devices, config_params.no_networking, root)

    redeploy_services_to_remove(trans, services_keypaths_to_remove, config_params.no_networking, root)
    
    handle_child_services_redeployment(logger, trans, kp_input, config_params, uinfo, service_groups)
    
    devices_diff_list = {}
    for device in devices:
        devices_diff_list[device] = [os.path.join(files.output_folder,
                                        "%s_before.cli" % (device)),
                                        os.path.join(files.output_folder,
                                        "%s_after.cli" % (device)),
                                        os.path.join(files.output_folder,
                                        "%s_before.xml" % (device)),
                                        os.path.join(files.output_folder,
                                        "%s_after.xml" % (device))]
    handle_final_service_readiness_check(logger, trans, kp_input, service_groups, uinfo, sock_maapi)

    has_parent, parent_path = get_parent(logger, uinfo, trans, kp_input, service_groups.services_list)
    logger.info("Generating Robot file")
    robot_service = None
    robot_service_modify = None
    if should_run_modify_workflow(config_params):
        robot_service_modify = RobotService(logger,
                                        kp_input,
                                        parent_path,
                                        xpath_node,
                                        plan_xpath,
                                        plan_kpath,
                                        files,
                                        devices_diff_list,
                                        pre_config_files,
                                        pre_config_devices,
                                        pre_config_xpaths,
                                        config_params.no_networking)
    else:
        robot_service = RobotService(logger,
                                kp_input,
                                parent_path,
                                xpath_node,
                                plan_xpath,
                                plan_kpath,
                                files,
                                devices_diff_list,
                                pre_config_files,
                                pre_config_devices,
                                pre_config_xpaths,
                                config_params.no_networking)
    return files.service_config_modify, files, robot_service, robot_service_modify
