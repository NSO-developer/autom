'''
    AUTOM helpers utils Folders class
    This class is responsible for creating the output folder structure for the test results
'''
import os
import ncs
from .tools import read_file, write_file

class Trans():
    def __init__(self, t, thandle, sock, uinfo):
        self.t = t
        self.thandle = thandle
        self.sock = sock
        self.uinfo = uinfo

class Folders():
    def __init__(self, folder_path, input_path, keypath_node, kp_input, trans):
        self.folder_path = folder_path
        self.input_path = input_path
        self.keypath_node = keypath_node
        self.kp_input = kp_input
        self.t = trans
        self.node_name = keypath_node._name
        self.output_folder = ""
        self.config_before_test_in_isolation_file_xml = ""
        self.cdb_diff_file_cli = ""
        self.config_before_file_clean_cli = ""
        self.config_after_file_clean_cli = ""
        self.dry_run_xml = ""
        self.dry_run_cli = ""
        self.dry_run_modify_xml = ""
        self.dry_run_modify_cli = ""
        self.dry_run_native = ""
        self.get_modif_file_xml = ""
        self.get_modif_file_cli = ""
        self.get_modif_modify_file_xml = ""
        self.get_modif_modify_file_cli = ""
        self.config_after_file_xml = ""
        self.config_before_file_xml = ""
        self.service_config_after_file_xml = ""
        self.service_config_modify = ""
        self.service_config_file_xml = ""
        self.test_folder = None

    def get_key_params(self):
        split_string = self.keypath_node._path.rsplit('{', 1)
        key_params = split_string[1].rstrip('}')
        return key_params.replace(' ', '_').replace('/', '%2f')

    def generate_xml_files(self):
        extension = 'xml'
        self.service_config_file_xml = os.path.join(self.output_folder,
                                               "service_config.%s" % extension)
        self.service_config_modify = os.path.join(
            self.output_folder, "service_config_modify.%s" % extension)
        self.service_config_after_file_xml = os.path.join(
            self.output_folder, "service_config_after.%s" % extension)
        self.config_after_file_xml = os.path.join(self.output_folder,
                                             "cdb_after.%s" % extension)
        self.config_before_file_xml = os.path.join(self.output_folder,
                                              "cdb_before.%s" % extension)
        self.get_modif_file_xml = os.path.join(self.output_folder,
                                 "get_modifications.%s" % extension)
        self.get_modifications_modify_file_xml = os.path.join(self.output_folder,
                                 "get_modifications_modify.%s" % extension)
        self.dry_run_xml = os.path.join(self.output_folder,
                                     "dry_run.%s" % extension)
        self.dry_run_modify_xml = os.path.join(self.output_folder,
                                     "dry_run_modify.%s" % extension)
        self.config_before_test_in_isolation_file_xml = os.path.join(
            self.output_folder, "cdb_before_test_in_isolation.%s" % extension)

    def generate_cli_files(self):
        extension = 'cli'
        self.config_after_file_clean_cli = os.path.join(self.output_folder,
                                                   "cdb_after.%s" % extension)
        self.config_before_file_clean_cli = os.path.join(
            self.output_folder, "cdb_before.%s" % extension)
        self.get_modif_file_cli = os.path.join(self.output_folder,
                                            "get_modifications.%s" % extension)
        self.cdb_diff_file_cli = os.path.join(self.output_folder,
                                            "cdb_diff.%s" % extension)
        self.dry_run_cli = os.path.join(self.output_folder,
                                                 "dry_run.%s" % extension)
        self.dry_run_modify_cli = os.path.join(self.output_folder,
                                                 "dry_run_modify.%s" % extension)
        self.dry_run_native = os.path.join(self.output_folder,
                                                 "dry_run.native")
        self.dry_run_modify_native = os.path.join(self.output_folder,
                                                 "dry_run_modify.native")
        self.get_modifications_modify_file_cli = os.path.join(self.output_folder,
                                            "get_modifications_modify.%s" % extension)
        
        

    def create_folder_env(self, service_config_modify, current_date_time, datetime, use_test):

        # Grabbing the key parameters for creating the output folder structure
        key_params = self.get_key_params()
        if service_config_modify is None and datetime == False and use_test:
            self.output_folder = os.path.join(self.folder_path, self.node_name, "test", key_params)
            self.test_folder = os.path.join(self.folder_path, self.node_name, "test")
            os.makedirs(self.output_folder, exist_ok=True)
            self.folder_path = self.output_folder
        elif service_config_modify is None and use_test and datetime == True:
            self.output_folder = os.path.join(self.folder_path, self.node_name, "test", key_params,
                                         current_date_time)
            self.test_folder = os.path.join(self.folder_path, self.node_name, "test")
            os.makedirs(self.output_folder, exist_ok=True)
            self.folder_path = self.output_folder
        elif service_config_modify is None and datetime == False:
            self.output_folder = os.path.join(self.folder_path, self.node_name, key_params)
            os.makedirs(self.output_folder, exist_ok=True)
            self.folder_path = self.output_folder
        elif service_config_modify is None and datetime == True:
            self.output_folder = os.path.join(self.folder_path, self.node_name, key_params,
                                         current_date_time)
            os.makedirs(self.output_folder, exist_ok=True)
            self.folder_path = self.output_folder
        elif service_config_modify is not None and use_test and datetime == False:
            self.output_folder = self.folder_path
            os.makedirs(self.output_folder, exist_ok=True)
            self.test_folder = os.path.join(self.input_path, self.node_name, "test")
        elif service_config_modify is not None and use_test:
            self.output_folder = os.path.join(self.folder_path, self.node_name, "test", key_params,
                                         current_date_time, "pos_modify")
            os.makedirs(self.output_folder, exist_ok=True)
            
            self.test_folder = os.path.join(self.input_path, self.node_name, "test", current_date_time)
        elif service_config_modify is not None and datetime == False:
            self.output_folder = os.path.join(self.folder_path, self.node_name, key_params,
                                         "pos_modify")
            os.makedirs(self.output_folder, exist_ok=True)
            
            self.test_folder = self.input_path
        elif service_config_modify is not None and datetime == True:
            self.output_folder = os.path.join(self.folder_path, self.node_name, key_params,
                                         current_date_time, "pos_modify")
            os.makedirs(self.output_folder, exist_ok=True)
            
            self.test_folder = self.input_path
        else:
            raise Exception("Unknown combination of use_test and datetime, error in creating output folder structure")
        #Generating the xml files
        self.generate_xml_files()
        if service_config_modify is not None:
            service_config_modify_file = read_file(service_config_modify)
            write_file(self.service_config_modify, service_config_modify_file)
        #Generating the cli files
        self.generate_cli_files()
