from abc import ABC,abstractmethod
from dataclasses import dataclass,field
@dataclass
class GenerationRequest:
    messages:list[dict[str,str]]
    system:str|None=None
    model:str|None=None
    max_tokens:int=1200
@dataclass
class GenerationResult:
    text:str
    model:str
    usage:dict[str,int]=field(default_factory=dict)
    estimated_cost_usd:float=0.0
class AIProvider(ABC):
    name:str
    @abstractmethod
    async def generate(self,request:GenerationRequest)->GenerationResult: ...
    @abstractmethod
    async def health_check(self)->bool: ...
