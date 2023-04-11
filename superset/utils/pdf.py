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
import io
import logging
import re
import urllib.request
from typing import Any, Dict, Optional
from urllib.error import URLError

import numpy as np
import pandas as pd
import simplejson
import pdfkit

from superset.utils.core import GenericDataType

logger = logging.getLogger(__name__)

def df_to_pdf(df: pd.DataFrame, **kwargs: Any) -> Any:
    # convert the pandas dataframe to html
    html = df.to_html()
    # convert html to pdf
    output = pdfkit.from_string(html, False)

    return output