from abc import ABC, abstractmethod
from copy import deepcopy
from io import StringIO
from typing import Dict, List, Union, Optional

import yaml


class WorkflowComponent(ABC):

    def __init__(self, id: str, component: Optional[Dict]):
        self._id = id
        if component is not None:
            if isinstance(component['inputs'], Dict):
                component['inputs'] = self._convert_inputs_from_dict_to_list(component['inputs'])
            if isinstance(component['outputs'], Dict):
                component['outputs'] = self._convert_inputs_from_dict_to_list(component['outputs'])

    @property
    def id(self):
        return self._id

    @abstractmethod
    def to_yaml(self, nested=False) -> str:
        pass

    @abstractmethod
    def to_dict(self) -> Dict:
        pass

    @property
    @abstractmethod
    def inputs(self) -> List[Dict]:
        pass

    @property
    @abstractmethod
    def outputs(self) -> List[Dict]:
        pass

    @classmethod
    def _convert_inputs_from_dict_to_list(cls, inputs: Dict) -> List[Dict]:
        return [{'id': id, **cwl_input} for id, cwl_input in inputs.items()]

    @classmethod
    def _convert_outputs_from_dict_to_list(cls, outputs: Dict) -> List[Dict]:
        return [{'id': id, **cwl_output} for id, cwl_output in outputs.items()]


class CWLTool(WorkflowComponent):

    def __init__(self, id: str, command_line_tool: Dict):
        super().__init__(id, command_line_tool)
        self._command_line_tool = command_line_tool

    @property
    def command_line_tool(self) -> Dict:
        return self._command_line_tool

    @command_line_tool.setter
    def command_line_tool(self, command_line_tool: Dict):
        self._command_line_tool = command_line_tool

    def to_yaml(self, nested=False) -> str:
        yaml_text = StringIO()
        yaml.dump(self.command_line_tool, yaml_text)

        return yaml_text.getvalue()

    def to_dict(self) -> Dict:
        return deepcopy(self.command_line_tool)

    @property
    def inputs(self) -> List[Dict]:
        return deepcopy(self._command_line_tool['inputs'])

    @property
    def outputs(self) -> List[Dict]:
        return deepcopy(self._command_line_tool['outputs'])

    def _packed_steps(self) -> Dict:
        to_return = self.to_dict()
        to_return.pop('cwlVersion')
        return to_return


class CWLWorkflow(WorkflowComponent):

    def __init__(self, id: str, workflow: Optional[Dict] = None) -> None:
        super().__init__(id, workflow)
        if workflow is None:
            self._inputs: List[Dict] = []
            self._outputs: List[Dict] = []
            self._steps: Dict = {}
            self._requirements: Dict = {}
        else:
            self._inputs: List[Dict] = deepcopy(workflow['inputs'])
            self._outputs: List[Dict] = deepcopy(workflow['outputs'])
            self._steps: Dict = deepcopy(workflow['steps'])
            self._requirements: Dict = deepcopy(workflow['requirements'])

    @property
    def steps(self):
        steps = {}
        for step in self._steps:
            steps[step] = deepcopy(self._steps[step])
            steps[step]['run'] = steps[step]['run']._id
        return deepcopy(steps)

    def _packed_steps(self):
        steps = {}
        for step in self._steps:
            s = deepcopy(self._steps[step])
            if isinstance(s['run'], WorkflowComponent):
                s['run'] = s['run']._packed_steps()
            steps[step] = s
        return deepcopy(steps)

    """
    A composite object can add or remove other components (both simple or
    complex) to or from its child list.
    """

    def add(self, component: WorkflowComponent, step_name: str) -> None:
        self._steps[step_name] = {
            'run': component,
            'in': {},
            'out': []
        }

    def remove(self, component: WorkflowComponent) -> None:
        raise NotImplementedError()

    def add_input(self, workflow_input: Dict, step_id: str, in_step_id: str):
        self._inputs.append(workflow_input)
        self._steps[step_id]['in'][in_step_id] = workflow_input['id']

    def to_yaml(self, nested=False) -> str:
        yaml_text = StringIO()
        if nested is True:
            result = self._to_packed_dict()
        else:
            result = self.to_dict()
        yaml.dump(result, yaml_text)
        yaml_str = yaml_text.getvalue()
        return yaml_str

    def _to_packed_dict(self) -> Dict:
        return {
            'cwlVersion': 'v1.0',
            'class': 'Workflow',
            'id': self.id,
            'inputs': self._inputs,
            'outputs': self._outputs,
            'steps': self._packed_steps(),
            'requirements': self._requirements
        }

    def to_dict(self) -> Dict:
        return {
            'cwlVersion': 'v1.0',
            'class': 'Workflow',
            'id': self.id,
            'inputs': self._inputs,
            'outputs': self._outputs,
            'steps': self.steps,
            'requirements': self._requirements
        }

    def validate(self):
        raise NotImplementedError()

    def add_step_in(self, step: str, name: str, connect: Union[str, dict]):
        self._steps[step]['in'][name] = deepcopy(connect)

    @property
    def inputs(self) -> List[Dict]:
        return deepcopy(self._inputs)

    @property
    def outputs(self) -> List[Dict]:
        return deepcopy(self._outputs)


class WorkflowComponentFactory():
    def get_workflow_component(self, yaml_string: str) -> WorkflowComponent:
        component = yaml.load(StringIO(yaml_string), yaml.SafeLoader)
        if 'id' not in component:
            raise ValueError("cwl must contains an id")
        if component['class'] == 'CommandLineTool':
            return CWLTool(component['id'], component)
        elif component['class'] == 'Workflow':
            return CWLWorkflow(component['id'], component)
        else:
            raise NotImplementedError(f"class f{component['class']} is not supported")


if __name__ == '__main__':
    pass
