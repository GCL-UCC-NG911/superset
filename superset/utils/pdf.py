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
    dashboar_title = f"<h2>{title}</h2>" if title else ""

    # loop filters
    filters_html = ""
    for element in filters:
        filter_name = element.get("name")
        filter_value = element.get("extraFormData").get("value")
        if filters_html == "":
            filters_html = f"<h1>{filter_name}: {filter_value}<h1>"
        else:
            filters_html = filters_html + f"<br><h1>{filter_name}: {filter_value}<h1>"

    # loop charts
    charts_html = ""
    for element in charts:
        chart_name = element.get("name")
        # html = df.to_html(index=False, justify="left")
        if charts_html == "":
            filters_html = f"<h1>{chart_name}<h1>"
        else:
            charts_html = charts_html + f"<br><h1>{chart_name}<h1>"

    # html_charts
    # update_query_context
    # get_chart_dataframe
    # convert pandas dataframe to html

    # concat all informations and convert html to pdf

    # convert html to pdf
    output = pdfkit.from_string(css + dashboar_title + filters_html + charts_html, False, options=options)
    return output
