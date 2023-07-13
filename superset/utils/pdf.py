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

css = """
<style>
    table {
        border-spacing: 0px;
        font-size: small;
    }
    th, td {
        padding: 2px 6px;
    }
</style>
"""


def df_to_pdf(df: pd.DataFrame, options: Dict = None, title: str = None) -> Any:
    title_header = f"<h2>{title}</h2>" if title else ""
    # convert the pandas dataframe to html
    html = df.to_html(index=False, justify="left")
    # convert html to pdf
    output = pdfkit.from_string(css + title_header + html, False, options=options)
    return output

def charts_to_pdf(auth_cookies: Dict[str, str], dashboard: Dict, charts: list, filters: list, options: Dict = None) -> Any:
    title = dashboard.get("dashboardTitle")
    dashboar_title = f"<h2>{title}</h2>"

    # loop filters
    # html_filters
    # filter_name= filter_value

    # loop charts
    # html_charts
    # update_query_context
    # get_chart_dataframe
    # convert pandas dataframe to html

    # concat all informations and convert html to pdf

    # convert html to pdf
    output = pdfkit.from_string(css + dashboar_title, False, options=options)
    return output
