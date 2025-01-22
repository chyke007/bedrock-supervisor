#!/usr/bin/env python3
import os

import aws_cdk as cdk

from agents_python.agents_python_stack import AgentsPythonStack
from agents_python.streamlit_stack import StreamlitStack


app = cdk.App()
bedrock_agent_stack = AgentsPythonStack(app, "AgentsPythonStack")
streamlit_stack = StreamlitStack(app, "StreamlitStack",
                               bedrock_agent_id=bedrock_agent_stack.bedrock_agent_id,
                               bedrock_agent_alias_id=bedrock_agent_stack.bedrock_agent_alias_id
                                 )

streamlit_stack.add_dependency(bedrock_agent_stack)

app.synth()
