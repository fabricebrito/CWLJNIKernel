#!/usr/bin/env cwl-runner

cwlVersion: v1.0
class: CommandLineTool
baseCommand: echo
id: echo
inputs:
  message:
    type: string
    inputBinding:
      position: 1
outputs:
  echo_output:
    type: stdout
