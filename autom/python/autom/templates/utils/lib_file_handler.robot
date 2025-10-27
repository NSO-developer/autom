*** Settings ***
Library    XML
Library    diff_config.py

*** Variables ***
${payloads_dir}  tests/data
${outputs_dir}  tests/data/outputs
# TODO can be used later for file paths. use or remove

*** Keywords ***
Compare xml ${input_file} to ${output_file}
    ${input_xml}=    Parse XML    ${input_file}
    ${output_xml}=    Parse XML    ${output_file}
    Elements Should Be Equal    ${input_xml}    ${output_xml}

Verify Two Files Have No Differences ${file1} ${file2}
    [Documentation]    Compares two files and asserts they are identical.
    Assert No Diff   ${file1}  ${file2}