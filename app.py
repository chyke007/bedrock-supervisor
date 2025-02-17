#!/usr/bin/env python3
import os

import aws_cdk as cdk

from agents_python.agent_stack import AgentStack
from agents_python.streamlit_stack import StreamlitStack


app = cdk.App()
agent_stack = AgentStack(app, "AgentStack")
streamlit_stack = StreamlitStack(app, "StreamlitStack",
                                 bedrock_agent_id=agent_stack.bedrock_supervisor_agent_id,
                                 bedrock_agent_alias_id=agent_stack.bedrock_supervisor_agent_alias_id
                                 )

streamlit_stack.add_dependency(agent_stack)

app.synth()
