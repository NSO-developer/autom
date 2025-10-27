# -*- mode: python; python-indent: 4 -*-
"""
AUTOM robot_generator
"""
import os
import re
import urllib.parse
from jinja2 import Template
from .xmlns_parser import parse_xmlns, write_xmlns
from .tools import (get_module_name_from_prefix,
                    strip_xpath_prefixes, read_file, write_file)

class RobotService:
    """
    RobotService class for generating Robot Framework test files
    
    This class uses the Files object from utils.py to access all file paths
    in a structured way, eliminating the need for many individual parameters.
    """
    
    def __init__(self, logger, service_path, parent_path, xpath_node, plan_xpath, 
                 plan_kpath, files, devices_diff_list, pre_config_files, 
                 pre_config_devices, pre_config_xpaths, no_networking):
        """
        Initialize RobotService with improved parameter handling
        
        Args:
            logger: Logger instance
            service_path: Service path string
            parent_path: Parent service path (optional)
            xpath_node: XPath node information
            plan_xpath: Plan XPath (optional)
            plan_kpath: Plan keypath (optional)
            files: Files object from utils.py containing all file paths
            devices_diff_list: Dictionary of device diff files
            pre_config_files: Dictionary of pre-configuration files
            pre_config_devices: List of pre-configuration devices
            no_networking: Boolean flag for networking mode
        """
        self.logger = logger
        self.service_path = self._make_service_path_restconf(service_path)
        self.service_path_original = service_path
        self.parent_path = self._make_service_path_restconf(parent_path) if parent_path else None
        self.no_networking = no_networking
        self.files = files
        
        # Initialize data structures
        self.device_data = {}
        self.pre_config_data = {}
        self.positive_modifications = []
        self.negative_modifications = []
        self.pre_config_devices = pre_config_devices
        
        # Process XPath node
        self._process_xpath_node(xpath_node)
        
        # Process plan information
        self._process_plan_info(plan_xpath, plan_kpath)
        
        # Setup file paths using Files object
        self._setup_file_paths()
        
        # Process device data
        self._process_device_data(devices_diff_list)
        
        # Process pre-config data
        self._process_pre_config_data(pre_config_files)
        
        logger.info("RobotService initialized for service: %s", self.service_path)
    
    def _process_xpath_node(self, xpath_node):
        """Process and encode XPath node information"""
        self.logger.info("Processing XPATH_NODE: %s", xpath_node)
        
        if xpath_node:
            xpath_node = strip_xpath_prefixes(xpath_node)
            xpath_node = xpath_node.replace("\"", "'")
            self.xpath_node = urllib.parse.quote(xpath_node.encode('utf8'), safe='')
        else:
            self.xpath_node = None
    
    def _process_plan_info(self, plan_xpath, plan_kpath):
        """Process plan-related information"""
        if plan_xpath is not None and plan_kpath is not None:
            self.plan_kpath = self._make_service_path_restconf(plan_kpath)
            self.plan_boolean = True
            self.logger.info("Plan enabled for service - kpath: %s", self.plan_kpath)
        else:
            self.plan_kpath = None
            self.plan_boolean = False
    
    def _setup_file_paths(self):
        """Setup file paths using the Files object with relative paths for Robot Framework"""
        base_path = self.files.input_path or self.files.output_folder
        
        # Core configuration files
        self.before_file = self._make_relative_path(self.files.config_before_file_xml, base_path)
        self.after_file = self._make_relative_path(self.files.config_after_file_xml, base_path)
        self.service_config = self._make_relative_path(self.files.service_config_file_xml, base_path)
        
        # Dry-run files
        self.dry_run_cli = self._make_relative_path(self.files.dry_run_cli, base_path)
        self.dry_run_xml = self._make_relative_path(self.files.dry_run_xml, base_path)
        
        # Modification files
        self.get_modifications_file_xml = self._make_relative_path(self.files.get_modifications_file_xml, base_path)
        self.get_modifications_file_cli = self._make_relative_path(self.files.get_modifications_file_cli, base_path)
        # Service modification files (if available)
        self._setup_modify_files(base_path)
        
        self.logger.info("File paths setup completed. Service config: %s", self.service_config)
    
    def _setup_modify_files(self, base_path):
        """Setup modification workflow file paths if available"""
        if hasattr(self.files, 'service_config_modify') and self.files.service_config_modify:
            self.service_config_modify = self._make_relative_path(
                self.files.service_config_modify, base_path)
            
            # Modification dry-run files
            if hasattr(self.files, 'dry_run_modify_xml'):
                self.dry_run_modify_xml = self._make_relative_path(
                    self.files.dry_run_modify_xml, base_path)
            if hasattr(self.files, 'dry_run_modify_cli'):
                self.dry_run_modify_cli = self._make_relative_path(
                    self.files.dry_run_modify_cli, base_path)
            
            # Modification change files
            if hasattr(self.files, 'get_modifications_modify_file_xml'):
                self.get_modifications_modify_file_xml = self._make_relative_path(
                    self.files.get_modifications_modify_file_xml, base_path)
            if hasattr(self.files, 'get_modifications_modify_file_cli'):
                self.get_modifications_modify_file_cli = self._make_relative_path(
                    self.files.get_modifications_modify_file_cli, base_path)

            self.logger.info("Service modification files setup: %s", self.service_config_modify)
        else:
            self.service_config_modify = None
            self.logger.info("No service modification files provided")
    
    def _make_relative_path(self, file_path, base_path):
        """Create a Robot Framework compatible relative path"""
        if not file_path:
            return None
        return os.path.join('${CURDIR}', os.path.relpath(file_path, base_path))
    
    def _process_device_data(self, devices_diff_list):
        """Process device diff file data"""
        if not devices_diff_list:
            return
        
        base_path = self.files.test_folder or self.files.output_folder
        
        for device, file_list in devices_diff_list.items():
            if device not in self.device_data:
                self.device_data[device] = []
            
            # Process each file in the device diff list
            for file_path in file_list:
                if file_path:  # Only process non-empty paths
                    relative_path = self._make_relative_path(file_path, base_path)
                    self.device_data[device].append(relative_path)
        
        self.logger.info("Processed device data for %d devices", len(self.device_data))
    
    def _process_pre_config_data(self, pre_config_files):
        """Process pre-configuration file data"""
        if not pre_config_files:
            return
        
        base_path = self.files.test_folder or self.files.output_folder
        
        for index, (key, value) in enumerate(pre_config_files.items(), 1):
            if value and len(value) > 0 and value[0]:  # Check if file path exists
                relative_path = self._make_relative_path(value[0], base_path)
                self.pre_config_data[f'pre_config{index}'] = relative_path
        
        self.logger.info("Processed pre-config data for %d configurations", len(self.pre_config_data))



    @staticmethod
    def _make_service_path(sp):
        return sp.replace('/ncs:services/', '/tailf-ncs:services/') \
            .replace('{', '=') \
            .replace(' ', ',') \
            .replace('}', '')
    @staticmethod
    def _make_service_path_restconf(sp):
        temp_var = sp.split("/")
        iter = 0
        rc_path = ''
        for item in temp_var:
            if ":" in item:
                prefix = item.split(":")
                module = get_module_name_from_prefix(prefix[0])
                if module is not None:
                    sp = sp.replace(prefix[0] + ":", module + ":", 1)
        temp_var = sp.split("}")
        count = 0
        return_string = ''
        for item in temp_var:
            #return_string +=item
            item = item + '}'
            temp_var1 = item.split('{')

            #return_string += item
            for part in temp_var1:
                if '}' in part:
                    part = part.replace('/', '%2f')
                    part = ('{' + part)
                return_string +=part

        return return_string.replace('{', '=') \
            .replace(' ', ',') \
            .replace('}', '').rstrip('=')


    def matches_service_path(self, sp):
        """
        Verify if the service path sp given as input matches with the service_path 
        attributes of the RobotService object after modification via _make_service_path_restconf

        Args:
            sp (str): A string representing the service path

        Returns:
            bool: True if the updated input service path matches the instance service_path
        """
        updated_sp = self._make_service_path_restconf(sp)
        return updated_sp == self.service_path

    @staticmethod
    def normalize_service_config(xml_file):
        """
        This function takes an xml file and normalize  the name
        of the file
        """
        tree = parse_xmlns(xml_file)
        xml_root = tree.getroot()
        folder = os.path.dirname(xml_file)
        file_name = os.path.basename(xml_file)
        normalized_name = os.path.join(folder, 'robot_%s' % file_name)
        write_xmlns(xml_root[0], normalized_name)
        return normalized_name

class RobotTestSuite:
    """
    RobotTestSuite
    """
    # ignoring R0903 too-few-public-methods
    # pylint: disable = R0903
    TEMPLATES_FOLDER = '../templates'
    UTILS_FOLDER = os.path.join(os.path.dirname(__file__),    
                                TEMPLATES_FOLDER,
                                'utils')
    TEST_SUITE_ROBOT = os.path.join(os.path.dirname(__file__),
                                    TEMPLATES_FOLDER,
                                    'robot_template.robot.j2')
    NSO_PRE_PROD_YAML = os.path.join(os.path.dirname(__file__),
                                    TEMPLATES_FOLDER,
                                    'robot_nso_pre_prod.yaml')
    NSO_LOCAL_YAML = os.path.join(os.path.dirname(__file__), 
                                  TEMPLATES_FOLDER,
                                  'robot_nso_local.yaml')
    #DEFAULT_TEST_SUITE_NAME = 'nso_service_testing'
    DEFAULT_TESTBED_NAME = 'nso_config.yaml'
    DIFF_CONFIG = os.path.join(os.path.dirname(__file__), 
                                UTILS_FOLDER,
                                'diff_config.py')
    ENCODE_PY = os.path.join(os.path.dirname(__file__), 
                             UTILS_FOLDER,
                             'encode.py')
    LIB_FILE_HANDLER = os.path.join(os.path.dirname(__file__), 
                                   UTILS_FOLDER,
                                   'lib_file_handler.robot')
    LIB_NSO_CONNECTION = os.path.join(os.path.dirname(__file__), 
                                     UTILS_FOLDER,
                                     'lib_nso_connection.robot')
    LIB_RESTCONF_CALLS = os.path.join(os.path.dirname(__file__), 
                                     UTILS_FOLDER,
                                     'lib_restconf_calls.robot')
    LIB_SERVICE_CALLS = os.path.join(os.path.dirname(__file__), 
                                    UTILS_FOLDER,
                                    'lib_service_calls.robot')
    

    def __init__(self,
                 services,
                 service_modify_list,
                 output_folder,
                 testbed,
                 test_suite_name,
                 datetime,
                 test_case_description,
                 environment,
                 add_to_previous,
                 outformat_cli_c):
        # ignorning R0913 too-many-arguments for __init__
        # pylint: disable = W0622 R0913
        self.test_suite_name = test_suite_name
        self.output_folder = output_folder
        self.services = services
        self.service_modify_list = service_modify_list
        self.testbed = testbed
        self.datetime = datetime
        self.test_case_description = test_case_description
        self.environment = environment
        self.add_to_previous = add_to_previous
        self.outformat_cli_c = outformat_cli_c

    def _render_test_suite(self):
        if self.add_to_previous == True:
            try:
                with open(RobotTestSuite.TEST_SUITE_ROBOT) as fd:
                    template = Template(fd.read())
                    diff_config = read_file(RobotTestSuite.DIFF_CONFIG)
                    diff_config_path = os.path.join(self.output_folder, 'diff_config.py')
                    write_file(diff_config_path, diff_config)
                    test_suite_file_name = "%s.robot" % self.test_suite_name
                    content = template.render(
                        services=self.services,
                        service_modify_list=self.service_modify_list,
                        testbed=self.testbed,
                        test_suite_file_name=test_suite_file_name,
                        datetime=self.datetime,
                        test_case_description=self.test_case_description,
                        add_to_previous=self.add_to_previous,
                        outformat_cli_c=self.outformat_cli_c) 
                    test_suite_path = os.path.join(self.output_folder,
                                                test_suite_file_name)
                    with open(test_suite_path, 'a') as f_out:
                        f_out.write('\n' + content)
                    return test_suite_path
            except Exception as e:
                raise IOError("Failed to generate test-suite %s (%s)!" %
                                    (test_suite_file_name, str(e))) from e
        elif self.add_to_previous == False:
            try:
                with open(RobotTestSuite.TEST_SUITE_ROBOT) as fd:
                    template = Template(fd.read())
                    diff_config = read_file(RobotTestSuite.DIFF_CONFIG)
                    encode_py = read_file(RobotTestSuite.ENCODE_PY)
                    lib_file_handler = read_file(RobotTestSuite.LIB_FILE_HANDLER)
                    lib_nso_connection = read_file(RobotTestSuite.LIB_NSO_CONNECTION)
                    lib_restconf_calls = read_file(RobotTestSuite.LIB_RESTCONF_CALLS)
                    lib_service_calls = read_file(RobotTestSuite.LIB_SERVICE_CALLS)
                    if self.environment == 'pre_prod':
                        topology_file = read_file(RobotTestSuite.NSO_PRE_PROD_YAML)
                    elif self.environment == 'nso_local':
                        topology_file = read_file(RobotTestSuite.NSO_LOCAL_YAML)
                    os.makedirs(self.output_folder + '/utils', exist_ok=True)
                    diff_config_path = os.path.join(self.output_folder, 'utils', 'diff_config.py')
                    encode_py_path = os.path.join(self.output_folder, 'utils', 'encode.py')
                    lib_file_handler_path = os.path.join(self.output_folder, 'utils', 'lib_file_handler.robot')
                    lib_nso_connection_path = os.path.join(self.output_folder, 'utils', 'lib_nso_connection.robot')
                    lib_restconf_calls_path = os.path.join(self.output_folder, 'utils', 'lib_restconf_calls.robot')
                    lib_service_calls_path = os.path.join(self.output_folder, 'utils', 'lib_service_calls.robot')
                    topology_file_path = os.path.join(self.output_folder, 'nso_config.yaml')
                    write_file(diff_config_path, diff_config)
                    write_file(encode_py_path, encode_py)
                    write_file(lib_file_handler_path, lib_file_handler)
                    write_file(lib_nso_connection_path, lib_nso_connection)
                    write_file(lib_restconf_calls_path, lib_restconf_calls)
                    write_file(lib_service_calls_path, lib_service_calls)
                    write_file(topology_file_path, topology_file)
                    test_suite_file_name = "%s.robot" % self.test_suite_name
                    content = template.render(
                            services=self.services,
                            service_modify_list=self.service_modify_list,
                            testbed=self.testbed,
                            test_suite_file_name=test_suite_file_name,
                            datetime=self.datetime,
                            test_case_description=self.test_case_description,
                            add_to_previous=self.add_to_previous,
                            outformat_cli_c=self.outformat_cli_c)
                    if self.datetime:
                        test_suite_file_name = "%s_%s.robot" % (self.test_suite_name,
                                                               self.datetime)
                    else:
                        test_suite_file_name = "%s.robot" % self.test_suite_name       
                    test_suite_path = os.path.join(self.output_folder,
                                                test_suite_file_name)
                    with open(test_suite_path, 'w+') as f_out:
                        f_out.write(content)
                return test_suite_path
            except Exception as e:
                raise IOError("Failed to generated test-suite %s (%s)!" %
                                (self.test_suite_name, str(e))) from e

    def _render_testbed(self, environment):
        if self.testbed is not None:
            return self.testbed

        # A testbed must be generated
        #try:
        with open(RobotTestSuite.TEMPLATES_FOLDER + '/robot_' + str(environment) + '.yaml') as fd:
            template = Template(fd.read())
        
            content = template.render()
            testbed_path = os.path.join(self.output_folder,
                                        RobotTestSuite.DEFAULT_TESTBED_NAME)
        with open(testbed_path, 'w+') as f_out:
            f_out.write(content)
        self.testbed = "%s" % RobotTestSuite.DEFAULT_TESTBED_NAME
        return self.testbed
        #except Exception as e:
        #    raise IOError("Failed to generated testbed for %s (%s)!" %
        ##                  (self.test_suite_name, str(e))) from e

    def render(self):
        """
        render the TestSuite
        """
        #testbed_path = self._render_testbed(self.environment)
        test_suite_path = self._render_test_suite()
        #return test_suite_path, testbed_path
