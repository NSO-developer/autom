*** Settings ***
Library    RequestsLibrary
Library    Collections
Library    OperatingSystem
Variables  ../nso_config.yaml


*** Variables ***
${BASE_URL}   ${nso_server.http_version}://${nso_server.host}:${nso_server.http_port}/restconf/data

*** Keywords ***

Get auth token
    ${auth_token}=    Get Environment Variable    NSO_AUTH_TOKEN
    RETURN  ${auth_token}

Set Headers for xml
    ${headers}=    Create Dictionary
    
    ${NSO_AUTH_TOKEN}   Get auth token 
    Set To Dictionary    ${headers}    Authorization=Basic ${NSO_AUTH_TOKEN}
    Set To Dictionary    ${headers}    Accept=application/vnd.yang.collection+xml
    Set To Dictionary    ${headers}    Content-type=application/yang-data+xml
    Log    Headers set to: ${headers}
    RETURN  ${headers}

Setup NSO RESTCONF Session with xml
    [Documentation]    Creates a RESTCONF session to NSO for the entire test suite.
    ${headers}        Set Headers for xml
    Create Session    restconf_session    ${BASE_URL}    verify=False    headers=${headers}
    Set Global Variable   ${RESTCONF_SESSION}   restconf_session
    Log To Console    NSO RESTCONF session 'restconf_session' created.


Teardown NSO RESTCONF Session
    [Documentation]    Closes the RESTCONF session after all tests are done.
    Delete All Sessions
    Log To Console    NSO RESTCONF session(s) deleted.
