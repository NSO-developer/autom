*** Settings ***

Library                SSHLibrary
Variables              ../nso_config.yaml

*** Variables ***

${alias}   CLI


*** Keywords ***

Connect to NSO CLI
   Open Connection     ${nso_server.host}    port=${nso_server.cli_port}   alias=${alias}
   Login               ${nso_server.cli_user}        ${nso_server.cli_pass}

Get NSO version
    ${output}=  Execute CLI Command   show ncs-state version
    RETURN    ${output}

Execute CLI Command
    [Arguments]  ${command}
    Switch Connection   ${alias} 
    ${output}=   Execute Command   ${command} 
    RETURN    ${output}

Connect and Execute NSO CLI Command ${cmd}
    Connect to NSO CLI
    Execute CLI Command  ${cmd}

Enable Collect Forward Diff
    ${command}=  Set Variable  configure\\\nset services global-settings collect-forward-diff true\\\ncommit\\\nexit
    ${output}=  Connect and Execute NSO CLI Command ${command}
 