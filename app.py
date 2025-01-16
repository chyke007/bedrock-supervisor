#!/usr/bin/env python3
import os

import aws_cdk as cdk

from agents_python.agents_python_stack import AgentsPythonStack


app = cdk.App()
AgentsPythonStack(app, "AgentsPythonStack")

app.synth()
