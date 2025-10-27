*** Settings ***
Library    RequestsLibrary
Library    Collections
Library    OperatingSystem
Library    JSONLibrary

*** Variables ***
${payloads_dir}  tests/data

*** Keywords ***
Prepare json payload from file ${file}
    ${json_data}    Load Json From File     ${payloads_dir}/${file}
    Log To Console    Filename: ${json_data}
    RETURN            ${json_data}

Create service instance from xml file ${file}
    ${resp}=    Load config from xml file ${file}
    RETURN  ${resp}

Get service instance ${service_path}
    ${resp}=    GET On Session    restconf_session    ${service_path}    expected_status=200
    Log To Console     *** Retrieved service instance ***
    RETURN    ${resp}

Load config from xml file ${file}
    ${xml_payload}=   OperatingSystem.Get File     ${file}
    ${xml_payload}=  Evaluate  re.sub('<config xmlns=.*>', '<data>', """${xml_payload}""")  re
    ${xml_payload}=  Evaluate  re.sub('\\n</config>', '\\n</data>', """${xml_payload}""", count=1, flags=re.MULTILINE)  re
    ${resp}=     PATCH On Session    restconf_session   ${BASE_URL}   data=${xml_payload}  expected_status=204

Create service instance from xml file ${file}
    ${resp}=    Load config from xml file ${file}
    RETURN  ${resp}
  
Create service instance from json file ${service_file}
    ${payload}=  Prepare json payload from file ${service_file}
    ${resp}=     POST On Session    restconf_session  /  json=${payload}  expected_status=201
    Status Should Be                 201  ${resp}

Delete service with path ${service_path}
    Log To Console     ${service_path}
    ${resp}=    DELETE On Session    restconf_session    ${service_path}    expected_status=204
    Log To Console     *** Deleted service instance ***

Dry Run ${dry_run_mode} Create service instance from xml file ${file}
    ${xml_path}       Join Path     ${payloads_dir}     ${file}
    ${xml_payload}=   OperatingSystem.Get File     ${xml_path}
    ${resp}=     POST On Session    restconf_session  /?dry-run\=${dry_run_mode}  data=${xml_payload}  expected_status=201

Dry-run ${dry_run_mode} on NSO using xml payload file ${file}
    ${xml_payload}=   OperatingSystem.Get File     ${file}
    ${xml_payload}=  Evaluate  re.sub('<config xmlns=.*>', '', """${xml_payload}""")  re
    ${xml_payload}=  Evaluate  re.sub('\\n</config>', '', """${xml_payload}""", count=1, flags=re.MULTILINE)  re
    ${resp}=     PATCH On Session    restconf_session    ${BASE_URL}?dry-run\=${dry_run_mode}  data=${xml_payload}  expected_status=200
    Log To Console     *** Run Action PATCH on Session RESTCONF towards NSO with Dry-Run using XML payload ***
    RETURN  ${resp.text}

Run Action Get-Modifications ${get_mod_mode} on NSO using XML payload with path ${path}
    ${xml_payload}=   Set Variable    <input><outformat>${get_mod_mode}</outformat></input>
    ${resp}=     POST On Session    restconf_session    ${path}/get-modifications  data=${xml_payload}  expected_status=200
    RETURN  ${resp.text}

Is service with path ${path} present on NSO
    TRY
      ${resp}=    Get service instance ${path}
      Status Should Be                 200  ${resp}
      RETURN    ${True}
    EXCEPT
      Log To Console    Service with path ${path} not present on NSO
      RETURN    ${False}
    END
