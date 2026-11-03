from datetime import datetime,timezone
from sqlalchemy import String,Text,DateTime,Float,JSON
from sqlalchemy.orm import Mapped,mapped_column
from packages.database.models.base import Base
def utcnow(): return datetime.now(timezone.utc)
class Opportunity(Base):
    __tablename__="opportunities"
    id:Mapped[int]=mapped_column(primary_key=True)
    title:Mapped[str]=mapped_column(String(250),index=True)
    company:Mapped[str]=mapped_column(String(250),default="")
    location:Mapped[str]=mapped_column(String(250),default="")
    description:Mapped[str]=mapped_column(Text,default="")
    source_url:Mapped[str]=mapped_column(String(2000),default="")
    status:Mapped[str]=mapped_column(String(40),default="discovered")
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
class Approval(Base):
    __tablename__="approvals"
    id:Mapped[int]=mapped_column(primary_key=True)
    action_type:Mapped[str]=mapped_column(String(80),index=True)
    payload:Mapped[dict]=mapped_column(JSON)
    rationale:Mapped[str]=mapped_column(Text)
    status:Mapped[str]=mapped_column(String(30),default="pending",index=True)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
class AIUsage(Base):
    __tablename__="ai_usage"
    id:Mapped[int]=mapped_column(primary_key=True)
    provider:Mapped[str]=mapped_column(String(40),index=True)
    model:Mapped[str]=mapped_column(String(120))
    input_tokens:Mapped[int]=mapped_column(default=0)
    output_tokens:Mapped[int]=mapped_column(default=0)
    estimated_cost_usd:Mapped[float]=mapped_column(Float,default=0)
    created_at:Mapped[datetime]=mapped_column(DateTime(timezone=True),default=utcnow)
