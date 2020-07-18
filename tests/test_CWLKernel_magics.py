import json
import logging
import os
import tarfile
import tempfile
import unittest
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
import yaml
from mockito import when, mock

from cwlkernel.CWLKernel import CWLKernel
from cwlkernel.cwlrepository.cwlrepository import WorkflowRepository


class TestCWLKernelMagics(unittest.TestCase):
    data_directory: str
    cwl_directory: str
    kernel_root_directory: str
    maxDiff = None

    def get_kernel(self) -> CWLKernel:
        kernel = CWLKernel()
        # cancel send_response
        kernel.send_response = lambda *args, **kwargs: None
        return kernel

    def setUp(self) -> None:
        import tempfile
        CWLKernel.clear_instance()
        WorkflowRepository(Path(tempfile.mkdtemp()))
        WorkflowRepository.get_instance().delete()

    @classmethod
    def setUpClass(cls) -> None:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)-15s:%(levelname)s:%(name)s:%(process)d:%(message)s'
        )
        cls.data_directory = os.sep.join([os.path.dirname(os.path.realpath(__file__)), 'input_data'])
        cls.cwl_directory = os.sep.join([os.path.dirname(os.path.realpath(__file__)), 'cwl'])
        cls.kernel_root_directory = tempfile.mkdtemp()

    def test_data_magic_command(self):
        from cwlkernel.CWLKernel import CWLKernel
        kernel = CWLKernel()
        # monitor responses
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        with open(os.sep.join([self.cwl_directory, 'echo_stdout.cwl'])) as f:
            workflow_str = f.read()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(workflow_str, False)
        )

        with open(os.sep.join([self.data_directory, 'echo-job.yml'])) as f:
            data = f"% execute echo\n{f.read()}"
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(data, False)
        )

        from lxml import etree
        kernel.do_execute('% data')
        self.assertEqual(
            1,
            len(etree.HTML(responses[-1][0][2]['data']['text/html']).xpath('//a'))
        )

    def test_display_data_magic_command(self):
        from cwlkernel.CWLKernel import CWLKernel
        kernel = CWLKernel()
        # monitor responses
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        with open(os.sep.join([self.cwl_directory, 'echo_stdout.cwl'])) as f:
            workflow_str = f.read()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(workflow_str, False)
        )

        with open(os.sep.join([self.data_directory, 'echo-job.yml'])) as f:
            data = f"% execute echo\n{f.read()}"
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(data, False)
        )

        kernel.do_execute('% displayData')
        self.assertEqual(
            'ERROR: you must select an output to display. Correct format:\n % displayData [output name]',
            responses[-1][0][2]['text']
        )

        kernel.do_execute('% displayData echo_output')
        self.assertEqual(
            'Hello world!\n',
            responses[-1][0][2]['text']
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(data, False)
        )
        self.assertEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% displayData echo_output')
        )
        self.assertEqual(
            'Hello world!\n',
            responses[-1][0][2]['text']
        )

    def test_logs_magic_command(self):
        from cwlkernel.CWLKernel import CWLKernel
        kernel = CWLKernel()
        # cancel send_response
        responses = []

        kernel.send_response = lambda *args, **kwargs: responses.extend(args[2]['data']['application/json'])
        exec_response = kernel.do_execute('% logs')
        self.assertDictEqual(
            {"status": "ok", "execution_count": 0, 'payload': [], 'user_expressions': {}},
            exec_response
        )
        exec_response = kernel.do_execute('% logs')
        self.assertDictEqual(
            {"status": "ok", "execution_count": 0, 'payload': [], 'user_expressions': {}},
            exec_response
        )
        number_of_responses = len(responses)
        self.assertEqual(number_of_responses, 2)
        exec_response = kernel.do_execute('% logs 1')
        self.assertDictEqual(
            {"status": "ok", "execution_count": 0, 'payload': [], 'user_expressions': {}},
            exec_response
        )
        self.assertEqual(len(responses), number_of_responses + 1)
        self.assertEqual(
            responses[0]['process_id']['process_id'],
            os.getpid()
        )

    def test_all_magic_commands_have_methods(self):
        kernel = CWLKernel()
        for magic_name, magic_function in kernel._magic_commands.items():
            hasattr(magic_function, '__call__')

    def test_display_json_output_after_execution(self):
        from cwlkernel.CWLKernel import CWLKernel
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        # prepare data
        with open(os.sep.join([self.data_directory, 'tar_job.yml'])) as f:
            data = f.read()
        tar_directory = kernel._cwl_executor.file_manager.ROOT_DIRECTORY
        with open(os.path.join(tar_directory, 'hello.txt'), 'w') as temp_hello_world_file:
            temp_hello_world_file.write("hello world")
        tar_full_name = os.path.join(tar_directory, 'tarfile.tar')
        print('create tar file:', tar_full_name)
        with tarfile.open(tar_full_name, 'w') as tar:
            tar.add(temp_hello_world_file.name)
        data = f"% execute extract-tar\n{data.format(tar_directory=tar_directory)}"

        # set workflow
        with open(os.sep.join([self.cwl_directory, 'extract_tar.cwl'])) as f:
            workflow_str = f.read().format(example_out=temp_hello_world_file.name[1:])

        result = kernel.do_execute(workflow_str, False)
        self.assertEqual('ok', result['status'], f'execution returned an error')

        result = kernel.do_execute(data, False)
        self.assertEqual('ok', result['status'], f'execution returned an error')

        self.assertDictEqual(
            {
                'example_out': {
                    'location': f'file://{tar_directory}/hello.txt', 'basename': 'hello.txt',
                    'nameroot': 'hello', 'nameext': '.txt', 'class': 'File',
                    'checksum': 'sha1$2aae6c35c94fcfb415dbe95f408b9ce91ee846ed', 'size': 11,
                    'http://commonwl.org/cwltool#generation': 0,
                    'id': 'example_out',
                    "result_counter": 0,
                    '_produced_by': 'extract-tar',
                }
            },
            responses[-1][0][2]['data']['application/json']
        )

        self.assertDictEqual(
            {
                'example_out': {
                    'location': f'file://{tar_directory}/hello.txt', 'basename': 'hello.txt',
                    'nameroot': 'hello', 'nameext': '.txt', 'class': 'File',
                    'checksum': 'sha1$2aae6c35c94fcfb415dbe95f408b9ce91ee846ed', 'size': 11,
                    'http://commonwl.org/cwltool#generation': 0,
                    'id': 'example_out',
                    "result_counter": 0,
                    '_produced_by': 'extract-tar',
                }
            },
            json.loads(responses[-1][0][2]['data']['text/plain'])
        )

    def test_snippet_builder(self):
        import yaml
        from cwlkernel.CWLKernel import CWLKernel
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        with open(os.sep.join([self.cwl_directory, 'echo.cwl'])) as f:
            echo_workflow = f.read().splitlines()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"% snippet add\n{os.linesep.join(echo_workflow[:6])}")
        )

        self.assertDictEqual(
            yaml.load(StringIO(os.linesep.join(echo_workflow[:6])), yaml.Loader),
            dict(responses[-1][0][2]['data']['application/json'])
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"% snippet build\n{os.linesep.join(echo_workflow[6:])}")
        )

        self.assertDictEqual(
            yaml.load(StringIO(os.linesep.join(echo_workflow)), yaml.Loader),
            dict(responses[-1][0][2]['data']['application/json'])
        )

        self.assertDictEqual(
            yaml.load(StringIO(kernel._workflow_repository.__repo__.get_by_id("echo").to_yaml()), yaml.Loader),
            yaml.load(StringIO('\n'.join(echo_workflow)), yaml.Loader),
        )

    def test_compose(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))
        with open(os.sep.join([self.cwl_directory, 'head.cwl'])) as f:
            head = f.read()
        with open(os.sep.join([self.cwl_directory, 'tail.cwl'])) as f:
            tail = f.read()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(head)
        )
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(tail)
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute("""% newWorkflow main
% newWorkflowAddStep tail tailstepid
% newWorkflowAddStep head headstepid
% newWorkflowAddInput headstepid headinput
id: inputfile
type: File
% newWorkflowAddStepIn tailstepid headstepid headoutput
tailinput: headstepid/headoutput
% newWorkflowAddOutputSource tailstepid/tailoutput File
% newWorkflowBuild""")
        )

        self.assertDictEqual(
            {
                "cwlVersion": "v1.0",
                "class": "Workflow",
                "id": "main",
                "inputs": [{'id': 'inputfile', 'type': 'File'}],
                "outputs": [{'id': 'tailoutput', 'type': 'File', 'outputSource': "tailstepid/tailoutput"}],
                "steps": {
                    "headstepid":
                        {
                            "run": "head.cwl",
                            "in": {"headinput": "inputfile"},
                            "out": ['headoutput']
                        },
                    "tailstepid":
                        {
                            "run": "tail.cwl",
                            "in": {"tailinput": "headstepid/headoutput"},
                            "out": ['tailoutput']
                        },
                },
                'requirements': {}
            },
            yaml.load(kernel._workflow_repository.get_by_id("main").to_yaml(), yaml.Loader),
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% execute main
inputfile: 
    class: File
    location: {os.path.join(self.data_directory, "data.csv")}""")
        )

    def test_githubImport(self):
        when(requests) \
            .get("https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/head.cwl?ref=dev") \
            .thenReturn(mock({
            'status_code': 200,
            'json': lambda: {
                "name": "head.cwl",
                "path": "tests/cwl/head.cwl",
                "sha": "74e6680835a37ecc696279bd84495a4ec370c732",
                "size": 316,
                "url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/head.cwl?ref=dev",
                "html_url": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/head.cwl",
                "git_url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/74e6680835a37ecc696279bd84495a4ec370c732",
                "download_url": "https://raw.githubusercontent.com/giannisdoukas/CWLJNIKernel/dev/tests/cwl/head.cwl",
                "type": "file",
                "content": "Y2xhc3M6IENvbW1hbmRMaW5lVG9vbApjd2xWZXJzaW9uOiB2MS4wCmlkOiBo\nZWFkCmJhc2VDb21tYW5kOgogIC0gaGVhZAppbnB1dHM6CiAgLSBpZDogbnVt\nYmVyX29mX2xpbmVzCiAgICB0eXBlOiBpbnQ/CiAgICBpbnB1dEJpbmRpbmc6\nCiAgICAgIHBvc2l0aW9uOiAwCiAgICAgIHByZWZpeDogJy1uJwogIC0gaWQ6\nIGhlYWRpbnB1dAogICAgdHlwZTogRmlsZQogICAgaW5wdXRCaW5kaW5nOgog\nICAgICBwb3NpdGlvbjogMQpvdXRwdXRzOgogIC0gaWQ6IGhlYWRvdXRwdXQK\nICAgIHR5cGU6IHN0ZG91dApsYWJlbDogaGVhZApzdGRvdXQ6IGhlYWQub3V0\nCg==\n",
                "encoding": "base64",
                "_links": {
                    "self": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/head.cwl?ref=dev",
                    "git": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/74e6680835a37ecc696279bd84495a4ec370c732",
                    "html": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/head.cwl"
                }
            }
        }))
        when(requests) \
            .get(
            "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/3stepWorkflow.cwl?ref=dev") \
            .thenReturn(mock(
            {
                'status_code': 200,
                'json': lambda: {
                    "name": "3stepWorkflow.cwl",
                    "path": "tests/cwl/3stepWorkflow.cwl",
                    "sha": "681de5be2005ab7258c33328140b33e0c42b891f",
                    "size": 810,
                    "url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/3stepWorkflow.cwl?ref=dev",
                    "html_url": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/3stepWorkflow.cwl",
                    "git_url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/681de5be2005ab7258c33328140b33e0c42b891f",
                    "download_url": "https://raw.githubusercontent.com/giannisdoukas/CWLJNIKernel/dev/tests/cwl/3stepWorkflow.cwl",
                    "type": "file",
                    "content": "IyEvdXNyL2Jpbi9lbnYgY3dsdG9vbApjd2xWZXJzaW9uOiB2MS4wCmNsYXNz\nOiBXb3JrZmxvdwppZDogdGhyZWVzdGVwcwppbnB1dHM6CiAgLSBpZDogaW5w\ndXRmaWxlCiAgICB0eXBlOiBGaWxlCiAgLSBpZDogcXVlcnkKICAgIHR5cGU6\nIHN0cmluZwpvdXRwdXRzOgogIG91dHB1dGZpbGU6CiAgICB0eXBlOiBGaWxl\nCiAgICBvdXRwdXRTb3VyY2U6IGdyZXAyL2dyZXBvdXRwdXQKICBvdXRwdXRm\naWxlMjoKICAgIHR5cGU6IEZpbGUKICAgIG91dHB1dFNvdXJjZTogZ3JlcHN0\nZXAvZ3JlcG91dHB1dAoKc3RlcHM6CiAgaGVhZDoKICAgIHJ1bjogaGVhZC5j\nd2wKICAgIGluOgogICAgICBoZWFkaW5wdXQ6IGlucHV0ZmlsZQogICAgb3V0\nOiBbaGVhZG91dHB1dF0KCiAgZ3JlcHN0ZXA6CiAgICBydW46IGdyZXAuY3ds\nCiAgICBpbjoKICAgICAgZ3JlcGlucHV0OiBoZWFkL2hlYWRvdXRwdXQKICAg\nICAgcXVlcnk6IHF1ZXJ5CiAgICAgIGxpbmVzX2JlbGxvdzoKICAgICAgICB2\nYWx1ZUZyb206ICR7cmV0dXJuIDU7fQogICAgb3V0OiBbZ3JlcG91dHB1dF0K\nICBncmVwMjoKICAgIHJ1bjogZ3JlcC5jd2wKICAgIGluOgogICAgICBncmVw\naW5wdXQ6IGdyZXBzdGVwL2dyZXBvdXRwdXQKICAgICAgcXVlcnk6CiAgICAg\nICAgdmFsdWVGcm9tOiAncXVlcnknCiAgICAgIGxpbmVzX2Fib3ZlOgogICAg\nICAgIHZhbHVlRnJvbTogJHtyZXR1cm4gNTt9CiAgICBvdXQ6IFtncmVwb3V0\ncHV0XQpyZXF1aXJlbWVudHM6CiAgU3RlcElucHV0RXhwcmVzc2lvblJlcXVp\ncmVtZW50OiB7fQogIElubGluZUphdmFzY3JpcHRSZXF1aXJlbWVudDoge30K\n",
                    "encoding": "base64",
                    "_links": {
                        "self": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/3stepWorkflow.cwl?ref=dev",
                        "git": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/681de5be2005ab7258c33328140b33e0c42b891f",
                        "html": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/3stepWorkflow.cwl"
                    }
                }
            }))
        when(requests) \
            .get("https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/grep.cwl?ref=dev") \
            .thenReturn(mock(
            {
                'status_code': 200,
                'json': lambda: {
                    "name": "grep.cwl",
                    "path": "tests/cwl/grep.cwl",
                    "sha": "a0ce6c241f90eafd0b4c489a1880368f2ceca1d9",
                    "size": 476,
                    "url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/grep.cwl?ref=dev",
                    "html_url": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/grep.cwl",
                    "git_url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/a0ce6c241f90eafd0b4c489a1880368f2ceca1d9",
                    "download_url": "https://raw.githubusercontent.com/giannisdoukas/CWLJNIKernel/dev/tests/cwl/grep.cwl",
                    "type": "file",
                    "content": "Y2xhc3M6IENvbW1hbmRMaW5lVG9vbApjd2xWZXJzaW9uOiB2MS4wCmlkOiBn\ncmVwCmJhc2VDb21tYW5kOgogIC0gZ3JlcAppbnB1dHM6CiAgLSBpZDogcXVl\ncnkKICAgIHR5cGU6IHN0cmluZwogICAgaW5wdXRCaW5kaW5nOgogICAgICBw\nb3NpdGlvbjogMAogIC0gaWQ6IGxpbmVzX2JlbGxvdwogICAgdHlwZTogaW50\nPwogICAgaW5wdXRCaW5kaW5nOgogICAgICBwb3NpdGlvbjogMQogICAgICBw\ncmVmaXg6ICctQScKICAtIGlkOiBsaW5lc19hYm92ZQogICAgdHlwZTogaW50\nPwogICAgaW5wdXRCaW5kaW5nOgogICAgICBwb3NpdGlvbjogMgogICAgICBw\ncmVmaXg6ICctQicKICAtIGlkOiBncmVwaW5wdXQKICAgIHR5cGU6IEZpbGUK\nICAgIGlucHV0QmluZGluZzoKICAgICAgcG9zaXRpb246IDEwCm91dHB1dHM6\nCiAgLSBpZDogZ3JlcG91dHB1dAogICAgdHlwZTogc3Rkb3V0CmxhYmVsOiBo\nZWFkCnN0ZG91dDogZ3JlcG91dHB1dC5vdXQ=\n",
                    "encoding": "base64",
                    "_links": {
                        "self": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/grep.cwl?ref=dev",
                        "git": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/a0ce6c241f90eafd0b4c489a1880368f2ceca1d9",
                        "html": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/grep.cwl"
                    }
                }
            }
        ))
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(
                "% githubImport https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/3stepWorkflow.cwl")
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% execute 3stepWorkflow
inputfile:
    class: File
    location: {os.sep.join([self.cwl_directory, '3stepWorkflow.cwl'])}
query: id""")
        )

    def test_githubImport_without_id(self):
        when(requests) \
            .get(
            "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/without_id.cwl?ref=dev") \
            .thenReturn(mock({
            'status_code': 200,
            'json': lambda: {
                "name": "without_id.cwl",
                "path": "tests/cwl/without_id.cwl",
                "sha": "8dd9d522c666d469c75bac566957e78acdb4a5f6",
                "size": 129,
                "url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/without_id.cwl?ref=dev",
                "html_url": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/without_id.cwl",
                "git_url": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/8dd9d522c666d469c75bac566957e78acdb4a5f6",
                "download_url": "https://raw.githubusercontent.com/giannisdoukas/CWLJNIKernel/dev/tests/cwl/without_id.cwl",
                "type": "file",
                "content": "Y3dsVmVyc2lvbjogdjEuMApjbGFzczogQ29tbWFuZExpbmVUb29sCmJhc2VD\nb21tYW5kOiBbZWNobywgImhlbGxvIHdvcmxkIl0KaW5wdXRzOiBbXQpvdXRw\ndXRzOgogIGV4YW1wbGVfb3V0cHV0OgogICAgdHlwZTogc3Rkb3V0\n",
                "encoding": "base64",
                "_links": {
                    "self": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/contents/tests/cwl/without_id.cwl?ref=dev",
                    "git": "https://api.github.com/repos/giannisdoukas/CWLJNIKernel/git/blobs/8dd9d522c666d469c75bac566957e78acdb4a5f6",
                    "html": "https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/without_id.cwl"
                }
            }}))

        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(
                "% githubImport https://github.com/giannisdoukas/CWLJNIKernel/blob/dev/tests/cwl/without_id.cwl")
        )
        self.assertRegex(responses[-1][0][2]['text'], r"^tool 'without_id' registered")

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% execute {responses[-1][0][2]['text'].split("'")[1]}""")
        )

    def test_sample_csv(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% displayDataCSV no-existing""")
        )
        self.assertEqual(
            'Result not found',
            responses[-1][0][2]['text']
        )

        with open(os.sep.join([self.cwl_directory, 'head.cwl'])) as f:
            head = f.read()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(head)
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% execute head 
        headinput:
            class: File
            location: {os.sep.join([self.data_directory, 'data.csv'])}
        number_of_lines: 15""")
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute("% sampleCSV headoutput 0.2")
        )

        shape = pd.read_html(responses[-1][0][2]['data']['text/html'], header=None)[0].shape
        print('shape:', shape)
        self.assertAlmostEqual(shape[0], 4, delta=4)
        self.assertEqual(shape[1], 20)

    def test_display_data_csv(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% displayDataCSV no-existing""")
        )
        self.assertEqual(
            'Result not found',
            responses[-1][0][2]['text']
        )

        with open(os.sep.join([self.cwl_directory, 'head.cwl'])) as f:
            head = f.read()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(head)
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% execute head 
headinput:
    class: File
    location: {os.sep.join([self.data_directory, 'data.csv'])}
number_of_lines: 15""")
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute("% displayDataCSV headoutput")
        )

        self.assertListEqual(
            [-54, -85, -5, 47, 39, 20, -58, 24, 12, 13, 4, -22, -1, -70, 44, -30, 91, -6, 40, -24],
            list(pd.read_html(responses[-1][0][2]['data']['text/html'], header=None)[0].values[0])
        )

    def test_magics_magic_command(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        commands = [f'\t- {cmd}' for cmd in kernel._magic_commands.keys()]
        commands.sort()

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% magics""")
        )
        self.assertEqual(
            'List of Available Magic commands\n' + os.linesep.join(commands),
            responses[-1][0][2]['text']
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"""% magics data""")
        )
        from cwlkernel.kernel_magics import data as data_magic_command
        import inspect
        self.assertEqual(
            inspect.getdoc(data_magic_command),
            responses[-1][0][2]['text']
        )
        self.assertIn(' '.join('Display all the data which are registered in the kernel session.'.split()),
                      ' '.join(responses[-1][0][2]['text'].split()))

    def test_view_magic_command(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))
        with open(os.sep.join([self.cwl_directory, 'head.cwl'])) as f:
            head = f.read()
        with open(os.sep.join([self.cwl_directory, 'tail.cwl'])) as f:
            tail = f.read()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(head)
        )
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(tail)
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute("""% newWorkflow main
% newWorkflowAddStep tail tailstepid
% newWorkflowAddStep head headstepid
% newWorkflowAddInput headstepid headinput
id: inputfile
type: File
% newWorkflowAddStepIn tailstepid headstepid headoutput
tailinput: headstepid/headoutput
% newWorkflowAddOutputSource tailstepid/tailoutput File
% newWorkflowBuild""")
        )

        self.assertDictEqual(
            {
                "cwlVersion": "v1.0",
                "class": "Workflow",
                "id": "main",
                "inputs": [{'id': 'inputfile', 'type': 'File'}],
                "outputs": [{'id': 'tailoutput', 'type': 'File', 'outputSource': "tailstepid/tailoutput"}],
                "steps": {
                    "headstepid":
                        {
                            "run": "head.cwl",
                            "in": {"headinput": "inputfile"},
                            "out": ['headoutput']
                        },
                    "tailstepid":
                        {
                            "run": "tail.cwl",
                            "in": {"tailinput": "headstepid/headoutput"},
                            "out": ['tailoutput']
                        },
                },
                'requirements': {}
            },
            yaml.load(kernel._workflow_repository.get_by_id("main").to_yaml(), yaml.Loader),
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% view main')
        )

        self.assertIn(
            'image/svg+xml',
            responses[-1][0][2]['data'])

    def test_scatter_tool(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        with open(os.path.join(self.cwl_directory, 'echo_stdout.cwl')) as f:
            yaml_tool = f.read()
        expected_tool = {
            'cwlVersion': 'v1.0',
            'id': 'scattered_echo',
            'class': 'Workflow',
            'inputs': [{'id': 'message_scatter_array', 'type': 'string[]'}],
            'outputs': [{'type': 'File[]', 'id': 'echo_output_scatter_array',
                         'outputSource': 'echo/echo_output'}],
            'steps': {'echo': {'run': 'echo.cwl',
                               'scatter': 'message',
                               'in': {'message': 'message_scatter_array'},
                               'out': ['echo_output']}},
            'requirements': {'ScatterFeatureRequirement': {}}
        }

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(yaml_tool)
        )
        self.assertDictEqual(
            {'status': 'error', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% scatter echo')
        )
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% scatter NOT-EXISTING-TOOL-ID message')
        )
        self.assertEqual(
            responses[-1][0][2]['name'], 'stderr'
        )
        self.assertEqual(
            responses[-1][0][2]['text'], "Tool 'NOT-EXISTING-TOOL-ID' not found"
        )
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% scatter echo NOT-EXISTING-INPUT')
        )
        self.assertEqual(
            responses[-1][0][2]['name'], 'stderr'
        )
        self.assertEqual(
            responses[-1][0][2]['text'], "There is no input 'NOT-EXISTING-INPUT' in tool 'echo'"
        )
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% scatter echo message')
        )
        scattered_tool = dict(responses[-1][0][2]['data']['application/json'])
        self.assertListEqual(
            expected_tool['inputs'],
            scattered_tool['inputs']
        )
        self.assertListEqual(
            expected_tool['outputs'],
            scattered_tool['outputs']
        )
        expected_tool['steps']['echo']['run'] = os.path.join(
            os.path.dirname(scattered_tool['steps']['echo']['run']), expected_tool['steps']['echo']['run']
        )
        self.assertDictEqual(
            expected_tool['steps'],
            scattered_tool['steps']
        )
        self.assertDictEqual(
            expected_tool,
            scattered_tool
        )
        self.assertIsNotNone(kernel.workflow_repository.get_instance().get_by_id(scattered_tool['id']))

    def test_system_magic_command(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute("% system echo 'Hello World'")
        )
        self.assertDictEqual(
            {'name': 'stdout', 'text': 'Hello World\n'},
            responses[-1][0][2],
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% system ls ERROR')
        )

        self.assertEqual(
            'stderr',
            responses[-1][0][2]['name'],
        )

    def test_edit_magic(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        with open(os.path.join(self.cwl_directory, 'echo_stdout.cwl')) as f:
            yaml_tool = f.read()
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(yaml_tool)
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute("% edit ")
        )

        self.assertEqual(
            responses[-1][0][2]['name'], 'stderr'
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute("% edit NOT-EXISTING")
        )
        self.assertEqual(
            responses[-1][0][2]['name'], 'stderr'
        )

        execute_response = kernel.do_execute("% edit echo")

        self.assertEqual('ok', execute_response['status'])
        self.assertListEqual(
            execute_response['payload'],
            [
                {
                    'source': "set_next_input",
                    'replace': True,
                    'text': f'% edit echo\n{kernel.workflow_repository.get_instance().get_by_id("echo").to_yaml()}',
                }
            ]
        )

        new_tool = yaml.safe_load(StringIO(yaml_tool))
        new_tool['outputs'] = {
            'new_echo_output': {'type': 'stdout'}
        }
        output = StringIO()
        yaml.safe_dump(new_tool, output)
        new_tool_yaml = output.getvalue()

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(f"% edit echo\n{new_tool_yaml}")
        )

        new_tool = kernel.workflow_repository.get_instance().get_by_id('echo')
        self.assertListEqual(
            new_tool.outputs,
            [{'id': 'new_echo_output', 'type': 'stdout'}]
        )

    def test_compile_executed_steps(self):
        kernel = CWLKernel()
        # cancel send_response
        responses = []
        kernel.send_response = lambda *args, **kwargs: responses.append((args, kwargs))

        with open(os.sep.join([self.cwl_directory, 'head-no-optional.cwl'])) as f:
            head_cwl = f.read()
        with open(os.sep.join([self.cwl_directory, 'tail-no-optional.cwl'])) as f:
            tail = f.read()

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(head_cwl)
        )
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(tail)
        )

        execute_tail = os.linesep.join([
            f"% execute tail",
            f"tailinput:",
            f"  class: File",
            f"  location: {os.sep.join([self.data_directory, 'data.csv'])}",
        ])
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(execute_tail)
        )

        execute_head = os.linesep.join([
            '% execute head',
            'headinput:',
            '  class: File',
            '  $data: tail/tailoutput',
        ])
        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute(execute_head)
        )

        self.assertDictEqual(
            {'status': 'ok', 'execution_count': 0, 'payload': [], 'user_expressions': {}},
            kernel.do_execute('% compile main')
        )
        expected_workflow = {
            'class': 'Workflow',
            'cwlVersion': "v1.0",
            'id': 'main',
            'inputs': [
                {
                    'id': 'tailinput',
                    'type': 'File'
                },
            ],
            'outputs': [
                {
                    'id': 'headoutput',
                    'type': 'File',
                    'outputSource': "head/headoutput"
                }
            ],
            "steps": {
                "head":
                    {
                        "run": "head.cwl",
                        "in": {
                            "headinput": "tail/tailoutput"
                        },
                        "out": ['headoutput']
                    },
                "tail":
                    {
                        "run": "tail.cwl",
                        "in": {"tailinput": "tailinput"},
                        "out": ['tailoutput']
                    },
            },
            'requirements': {}
        }
        self.assertDictEqual(
            expected_workflow,
            responses[-1][0][2]['data']['application/json']
        )

        self.assertDictEqual(
            expected_workflow,
            kernel.workflow_repository.get_instance().get_by_id('main').to_dict()
        )


if __name__ == '__main__':
    unittest.main()