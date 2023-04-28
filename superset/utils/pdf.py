# NGLS - EXCLUSIVE #
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
from typing import Any, Dict

import pandas as pd
import pdfkit

def df_to_pdf(df: pd.DataFrame, options: Dict = None) -> Any:
    # convert the pandas dataframe to html
    html = df.to_html(border=1, style='border-style: single; font-size: 12px;')
    # convert html to pdf
    output = pdfkit.from_string(html, False, options=options)

    return output