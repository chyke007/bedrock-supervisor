#!/usr/bin/env python3
import os

import aws_cdk as cdk

from agents_python.reservation_stack import ReservationStack
from agents_python.streamlit_stack import StreamlitStack


app = cdk.App()
reservation_stack = ReservationStack(app, "ReservationStack")
streamlit_stack = StreamlitStack(app, "StreamlitStack",
                               bedrock_agent_id=reservation_stack.bedrock_agent_id,
                               bedrock_agent_alias_id=reservation_stack.bedrock_agent_alias_id
                                 )

streamlit_stack.add_dependency(reservation_stack)

app.synth()
