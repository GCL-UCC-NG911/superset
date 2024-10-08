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
from enum import Enum
from typing import Set


class ChartDataResultFormat(str, Enum):
    """
    Chart data response format
    """

    CSV = "csv"
    JSON = "json"
    XLSX = "xlsx"
    # NGLS - BEGIN #
    PDF = "pdf"
    # NGLS - END #

    @classmethod
    def table_like(cls) -> Set["ChartDataResultFormat"]:
        # NGLS - BEGIN #
        return {cls.CSV} | {cls.XLSX} | {cls.PDF}
        # NGLS - END #


class ChartDataResultType(str, Enum):
    """
    Chart data response type
    """

    COLUMNS = "columns"
    FULL = "full"
    QUERY = "query"
    RESULTS = "results"
    SAMPLES = "samples"
    TIMEGRAINS = "timegrains"
    POST_PROCESSED = "post_processed"
    DRILL_DETAIL = "drill_detail"
