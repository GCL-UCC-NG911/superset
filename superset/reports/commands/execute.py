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
import json
import logging
from datetime import datetime, timedelta

# NGLS - BEGIN #
from io import BytesIO

# NGLS - END #
from typing import Any, List, Optional, Union
from uuid import UUID

import pandas as pd
from celery.exceptions import SoftTimeLimitExceeded

# NGLS - BEGIN #
from PIL import Image

# NGLS - END #
from sqlalchemy.orm import Session

from superset import app, security_manager
from superset.commands.base import BaseCommand
from superset.commands.exceptions import CommandException
from superset.common.chart_data import ChartDataResultFormat, ChartDataResultType
from superset.dashboards.permalink.commands.create import (
    CreateDashboardPermalinkCommand,
)
from superset.errors import ErrorLevel, SupersetError, SupersetErrorType
from superset.exceptions import SupersetErrorsException, SupersetException
from superset.extensions import feature_flag_manager, machine_auth_provider_factory
from superset.reports.commands.alert import AlertCommand
from superset.reports.commands.exceptions import (
    ReportScheduleAlertGracePeriodError,
    ReportScheduleClientErrorsException,
    ReportScheduleCsvFailedError,
    ReportScheduleCsvTimeout,
    ReportScheduleDataFrameFailedError,
    ReportScheduleDataFrameTimeout,
    ReportScheduleExecuteUnexpectedError,
    ReportScheduleNotFoundError,
    # NGLS - BEGIN #
    ReportSchedulePdfFailedError,
    ReportSchedulePdfTimeout,
    # NGLS - END #
    ReportSchedulePreviousWorkingError,
    ReportScheduleScreenshotFailedError,
    ReportScheduleScreenshotTimeout,
    ReportScheduleStateNotFoundError,
    ReportScheduleSystemErrorsException,
    ReportScheduleUnexpectedError,
    ReportScheduleWorkingTimeoutError,
)
from superset.reports.dao import (
    REPORT_SCHEDULE_ERROR_NOTIFICATION_MARKER,
    ReportScheduleDAO,
)
from superset.reports.models import (
    ReportDataFormat,
    ReportExecutionLog,
    ReportRecipients,
    ReportRecipientType,
    ReportSchedule,
    ReportScheduleType,
    ReportSourceFormat,
    ReportState,
)
from superset.reports.notifications import create_notification
from superset.reports.notifications.base import NotificationContent
from superset.reports.notifications.exceptions import NotificationError
from superset.tasks.utils import get_executor
from superset.utils.celery import session_scope
from superset.utils.core import HeaderDataType, override_user
from superset.utils.csv import get_chart_csv_data, get_chart_dataframe

# NGLS - BEGIN #
from superset.utils import pdf
from superset.charts.data.commands.get_data_command import ChartDataCommand
from typing import Any, Dict, Optional
from superset.connectors.base.models import BaseDatasource
from superset.charts.commands.exceptions import (
    ChartDataCacheLoadError,
    ChartDataQueryFailedError,
)
from superset.charts.data.query_context_cache_loader import QueryContextCacheLoader
from superset.charts.schemas import ChartDataQueryContextSchema
from superset.common.query_context import QueryContext
from marshmallow import ValidationError
from superset.views.base import (
    CsvResponse,
    generate_download_headers,
    generate_filename,
    PdfResponse,
    XlsxResponse,
)
from superset.charts.post_processing import apply_post_process
from superset.utils.screenshots import DashboardChartScreenshot
# NGLS - END #
from superset.utils.screenshots import ChartScreenshot, DashboardScreenshot
from superset.utils.urls import get_url_path

logger = logging.getLogger(__name__)


class BaseReportState:
    current_states: List[ReportState] = []
    initial: bool = False

    def __init__(
        self,
        session: Session,
        report_schedule: ReportSchedule,
        scheduled_dttm: datetime,
        execution_id: UUID,
    ) -> None:
        self._session = session
        self._report_schedule = report_schedule
        self._scheduled_dttm = scheduled_dttm
        self._start_dttm = datetime.utcnow()
        self._execution_id = execution_id

    def update_report_schedule_and_log(
        self,
        state: ReportState,
        error_message: Optional[str] = None,
    ) -> None:
        """
        Update the report schedule state et al. and reflect the change in the execution
        log.
        """
        self.update_report_schedule(state)
        self.create_log(error_message)

    def update_report_schedule(self, state: ReportState) -> None:
        """
        Update the report schedule state et al.

        When the report state is WORKING we must ensure that the values from the last
        execution run are cleared to ensure that they are not propagated to the
        execution log.
        """

        if state == ReportState.WORKING:
            self._report_schedule.last_value = None
            self._report_schedule.last_value_row_json = None

        self._report_schedule.last_state = state
        self._report_schedule.last_eval_dttm = datetime.utcnow()

        self._session.merge(self._report_schedule)
        self._session.commit()

    def create_log(self, error_message: Optional[str] = None) -> None:
        """
        Creates a Report execution log, uses the current computed last_value for Alerts
        """
        log = ReportExecutionLog(
            scheduled_dttm=self._scheduled_dttm,
            start_dttm=self._start_dttm,
            end_dttm=datetime.utcnow(),
            value=self._report_schedule.last_value,
            value_row_json=self._report_schedule.last_value_row_json,
            state=self._report_schedule.last_state,
            error_message=error_message,
            report_schedule=self._report_schedule,
            uuid=self._execution_id,
        )
        self._session.add(log)
        self._session.commit()

    def _get_url(
        self,
        user_friendly: bool = False,
        result_format: Optional[ChartDataResultFormat] = None,
        **kwargs: Any,
    ) -> str:
        """
        Get the url for this report schedule: chart or dashboard
        """
        force = "true" if self._report_schedule.force_screenshot else "false"
        if self._report_schedule.chart:
            if result_format in {
                ChartDataResultFormat.CSV,
                ChartDataResultFormat.JSON,
            }:
                return get_url_path(
                    "ChartDataRestApi.get_data",
                    pk=self._report_schedule.chart_id,
                    format=result_format.value,
                    type=ChartDataResultType.POST_PROCESSED.value,
                    force=force,
                )
            return get_url_path(
                "ExploreView.root",
                user_friendly=user_friendly,
                form_data=json.dumps({"slice_id": self._report_schedule.chart_id}),
                force=force,
                **kwargs,
            )

        # If we need to render dashboard in a specific state, use stateful permalink
        dashboard_state = self._report_schedule.extra.get("dashboard")
        if dashboard_state:
            permalink_key = CreateDashboardPermalinkCommand(
                dashboard_id=str(self._report_schedule.dashboard_id),
                state=dashboard_state,
            ).run()
            return get_url_path("Superset.dashboard_permalink", key=permalink_key)

        return get_url_path(
            "Superset.dashboard",
            user_friendly=user_friendly,
            dashboard_id_or_slug=self._report_schedule.dashboard_id,
            force=force,
            **kwargs,
        )

    def _get_screenshots(self) -> List[bytes]:
        """
        Get chart or dashboard screenshots
        :raises: ReportScheduleScreenshotFailedError
        """
        url = self._get_url()
        _, username = get_executor(
            executor_types=app.config["ALERT_REPORTS_EXECUTE_AS"],
            model=self._report_schedule,
        )
        user = security_manager.find_user(username)
        if self._report_schedule.chart:
            screenshot: Union[ChartScreenshot, DashboardScreenshot] = ChartScreenshot(
                url,
                self._report_schedule.chart.digest,
                window_size=app.config["WEBDRIVER_WINDOW"]["slice"],
                thumb_size=app.config["WEBDRIVER_WINDOW"]["slice"],
            )
        else:
            screenshot = DashboardScreenshot(
                url,
                self._report_schedule.dashboard.digest,
                window_size=app.config["WEBDRIVER_WINDOW"]["dashboard"],
                thumb_size=app.config["WEBDRIVER_WINDOW"]["dashboard"],
            )
        try:
            image = screenshot.get_screenshot(user=user)
        except SoftTimeLimitExceeded as ex:
            logger.warning("A timeout occurred while taking a screenshot.")
            raise ReportScheduleScreenshotTimeout() from ex
        except Exception as ex:
            raise ReportScheduleScreenshotFailedError(
                f"Failed taking a screenshot {str(ex)}"
            ) from ex
        if not image:
            raise ReportScheduleScreenshotFailedError()
        return [image]

    # NGLS - BEGIN #
    def _send_chart_response(
        self,
        result: Dict[Any, Any],
        form_data: Optional[Dict[str, Any]] = None,
        datasource: Optional[BaseDatasource] = None,
    ) -> Optional[Any]:
        result_type = result["query_context"].result_type
        result_format = result["query_context"].result_format

        logger.info("### _send_chart_response 0")
        logger.info(form_data)
         # Post-process the data so it matches the data presented in the chart.
        # This is needed for sending reports based on text charts that do the
        # post-processing of data, eg, the pivot table.
        logger.info(result_type)
        logger.info(result_format)
        if result_type == ChartDataResultType.POST_PROCESSED:
            result = apply_post_process(result, form_data, datasource)
            logger.info("### _send_chart_response 1")
            logger.info(result)
        if result_format in ChartDataResultFormat.table_like():
            logger.info("### _send_chart_response 2")
            # Verify user has permission to export file
            if not security_manager.can_access("can_csv", "Superset"):
                return None

            if not result["queries"]:
                return None

            if len(result["queries"]) == 1:
                # logger.info("### _send_chart_response 3")
                # return single query results
                data = result["queries"][0]["data"]
                logger.info(data)
                # NGLS - BEGIN #
                if result_format == ChartDataResultFormat.PANDAS:
                    logger.info("### _send_chart_response 5")
                    return data
                # NGLS - END #
        return None

    def _get_data_response(
        self,
        command: ChartDataCommand,
        force_cached: bool = True,
        form_data: Optional[Dict[str, Any]] = None,
        datasource: Optional[BaseDatasource] = None,
    ) -> Any:
        try:
            logger.info("### _get_data_response 0 0")
            result = command.run(force_cached=force_cached)
            logger.info(result)
        except ChartDataCacheLoadError as exc:
            logger.error(exc.message)
        except ChartDataQueryFailedError as exc:
            logger.error(exc.message)
        logger.info("### _get_data_response 1")
        return self._send_chart_response(result, form_data, datasource)

    # pylint: disable=invalid-name, no-self-use
    def _load_query_context_form_from_cache(self, cache_key: str) -> Dict[str, Any]:
        return QueryContextCacheLoader.load(cache_key)

    # pylint: disable=no-self-use
    def _create_query_context_from_form(
        self, form_data: Dict[str, Any]
    ) -> QueryContext:
        try:
            return ChartDataQueryContextSchema().load(form_data)
        except KeyError as ex:
            raise ValidationError("Request is incorrect") from ex
        except ValidationError as error:
            raise error

    def getAllTables(self, props, slices, filters, element) -> Optional[Any]:
        if props == None or element == None or element == '':
            return []
        
        # logger.info(element)
        # logger.info(props)
        childrenElement = props[element]
        # logger.info(childrenElement)

        if childrenElement['type'] == 'CHART':
            dataframe = None
            for slice in slices:
                if slice['slice_id'] == childrenElement['meta']['chartId']:
                    logger.info("### ### slice_id") 
                    logger.info(slice)
                    # TODO: protection
                    if slice['query_context'] != None:
                        form_data = json.loads(slice['query_context'])
                        for filter in filters:
                            if filter['filterType'] == 'filter_time':
                                if filter['value'] != '':
                                    for query in form_data['queries']:
                                        if 'time_range' in query:
                                            query['time_range'] = filter['value']
                                    form_data['form_data']['time_range'] = filter['value']

                        logger.info(form_data)
                        form_data['result_format'] = "pandas"
                        query_context = self._create_query_context_from_form(form_data)
                        command = ChartDataCommand(query_context)
                        command.validate()
                        dataframe = self._get_data_response(command, form_data=form_data, datasource=query_context.datasource)

            return [
                {
                    'chartId': childrenElement['meta']['chartId'],
                    'sliceName': childrenElement['meta']['sliceName'],
                    'uuid': childrenElement['meta']['uuid'],
                    'height': childrenElement['meta']['height'],
                    'width': childrenElement['meta']['width'],
                    'dataframe': dataframe,
                    'type': 'CHART',
                },
            ]

        if childrenElement['type'] == 'MARKDOWN':
            return [
                {
                    'code': childrenElement['meta']['code'],
                    'height': childrenElement['meta']['height'],
                    'width': childrenElement['meta']['width'],
                    'type': 'MARKDOWN',
                },
            ]

        alltables = []
        for children in childrenElement['children']:
            tables = self.getAllTables(props, slices, filters, children)
            # logger.info(tables)
            for table in tables:
                alltables.append(table)

        return alltables
    
    def getAllFilters(self, nativeFilters) -> Optional[Any]:
        if nativeFilters == None:
            return []
        
        allfilters = []
        for element in nativeFilters:
            value = ''
            if "value" in element['defaultDataMask']['filterState']:
                value = element['defaultDataMask']['filterState']['value']

            allfilters.append({
                'filterId': element['id'],
                'name': element['name'],
                'extraFormData': element['defaultDataMask']['extraFormData'],
                'value': value,
                'filterType': element['filterType'],
                'type': 'FILTER',
            })


        return allfilters

    def get_pdf_image(self) -> Optional[bytes]:
        logger.info("##### get_pdf_image 0")
        dashboardData = self._report_schedule.dashboard.data
        native_filter_configuration = self._report_schedule.dashboard.data['metadata']['native_filter_configuration']
        position_json = json.loads(self._report_schedule.dashboard.position_json)
        slices = self._report_schedule.dashboard.data['slices']
        
        logger.info(self._report_schedule.dashboard.data)

        dashboard = {}
        dashboard['dashboardId'] = dashboardData['id']
        dashboard['dashboardTitle'] = dashboardData['dashboard_title']
        dashboard['type'] = 'DASHBOARD'

        filters = self.getAllFilters(native_filter_configuration) 
        # charts = self.getAllTables(position_json,'ROOT_ID')
        format == "data_pdf"
        formData = [dashboard]
        formData.extend(filters)
        formData.extend(self.getAllTables(position_json, slices, filters, 'ROOT_ID'))
        
        logger.info(formData)

        # test = self._report_schedule.dashboard.charts
        # logger.info("##### self._report_schedule.dashboard.charts")
        # logger.info(test)
        # test = self._report_schedule.dashboard.position_json
        # logger.info("##### self._report_schedule.dashboard.position_json")
        # logger.info(test)
        # test = self._report_schedule.dashboard.filter_sets
        # logger.info("##### self._report_schedule.dashboard.filter_sets")
        # logger.info(test)
        # test = self._report_schedule.dashboard.sqla_metadata
        # logger.info("##### self._report_schedule.dashboard.sqla_metadata")
        # logger.info(test)
        # test = self._report_schedule.dashboard.data
        # logger.info("##### self._report_schedule.dashboard.data")
        # logger.info(test)
        # dashboard_id = self._report_schedule.dashboard.data['id']
        # native_filter_configuration = self._report_schedule.dashboard.data['metadata']['native_filter_configuration']
        # dashboard_title = self._report_schedule.dashboard.data['dashboard_title']
        # form_data = self._report_schedule.dashboard.data['slices'][0]['form_data']
        # query_context = self._report_schedule.dashboard.data['slices'][0]['query_context']
        # slice_id = self._report_schedule.dashboard.data['slices'][0]['slice_id']
        # slice_name = self._report_schedule.dashboard.data['slices'][0]['slice_name']
        # slice_form_data = self._report_schedule.dashboard.data['slices'][1]['form_data']
        # logger.info(query_context)
        
        logger.info("##### get_pdf_image 1")
        data = DashboardChartScreenshot('admin', {'formData': formData}, format, dashboardData['id']).get3()
        logger.info("##### end get_pdf_image #####")
        
        return data.read()

    def get_all_pdf_image(self) -> Optional[bytes]:
        images = []
        logger.info("##### start get_all_pdf_image #####")
        logger.info(vars(self))
        snapshots = self._get_screenshots()

        for snap in snapshots:
            logger.info("##### snap #####")
            img = Image.open(BytesIO(snap))
            if img.mode == "RGBA":
                img = img.convert("RGB")
            images.append(img)

        new_pdf = BytesIO()
        images[0].save(new_pdf, "PDF", save_all=True, append_images=images[1:])
        new_pdf.seek(0)
        logger.info("##### end get_all_pdf_image #####")
        return new_pdf.read()

    def get_pdf_data(self) -> bytes:
        url = self._get_url(result_format=ChartDataResultFormat.JSON)
        _, username = get_executor(
            executor_types=app.config["ALERT_REPORTS_EXECUTE_AS"],
            model=self._report_schedule,
        )
        user = security_manager.find_user(username)
        auth_cookies = machine_auth_provider_factory.instance.get_auth_cookies(user)

        logger.info("self._report_schedule.chart.query_context")
        logger.info(self._report_schedule.chart.query_context)

        if self._report_schedule.chart.query_context is None:
            logger.warning("No query context found, taking a screenshot to generate it")
            self._update_query_context()

        try:
            config = app.config
            logger.info("Getting chart from %s as user %s", url, user.username)
            dataframe = get_chart_dataframe(url, auth_cookies)
            pdf_data = pdf.df_to_pdf(dataframe, config["PDF_EXPORT"])
        except SoftTimeLimitExceeded as ex:
            raise ReportSchedulePdfTimeout() from ex
        except Exception as ex:
            raise ReportSchedulePdfFailedError(
                f"Failed generating pdf {str(ex)}"
            ) from ex
        if not pdf_data:
            raise ReportSchedulePdfFailedError()
        return pdf_data

    # NGLS - END #

    def _get_csv_data(self) -> bytes:
        url = self._get_url(result_format=ChartDataResultFormat.CSV)
        _, username = get_executor(
            executor_types=app.config["ALERT_REPORTS_EXECUTE_AS"],
            model=self._report_schedule,
        )
        user = security_manager.find_user(username)
        auth_cookies = machine_auth_provider_factory.instance.get_auth_cookies(user)

        if self._report_schedule.chart.query_context is None:
            logger.warning("No query context found, taking a screenshot to generate it")
            self._update_query_context()

        try:
            logger.info("Getting chart from %s as user %s", url, user.username)
            csv_data = get_chart_csv_data(chart_url=url, auth_cookies=auth_cookies)
        except SoftTimeLimitExceeded as ex:
            raise ReportScheduleCsvTimeout() from ex
        except Exception as ex:
            raise ReportScheduleCsvFailedError(
                f"Failed generating csv {str(ex)}"
            ) from ex
        if not csv_data:
            raise ReportScheduleCsvFailedError()
        return csv_data

    def _get_embedded_data(self) -> pd.DataFrame:
        """
        Return data as a Pandas dataframe, to embed in notifications as a table.
        """
        url = self._get_url(result_format=ChartDataResultFormat.JSON)
        _, username = get_executor(
            executor_types=app.config["ALERT_REPORTS_EXECUTE_AS"],
            model=self._report_schedule,
        )
        user = security_manager.find_user(username)
        auth_cookies = machine_auth_provider_factory.instance.get_auth_cookies(user)

        if self._report_schedule.chart.query_context is None:
            logger.warning("No query context found, taking a screenshot to generate it")
            self._update_query_context()

        try:
            logger.info("Getting chart from %s as user %s", url, user.username)
            dataframe = get_chart_dataframe(url, auth_cookies)
        except SoftTimeLimitExceeded as ex:
            raise ReportScheduleDataFrameTimeout() from ex
        except Exception as ex:
            raise ReportScheduleDataFrameFailedError(
                f"Failed generating dataframe {str(ex)}"
            ) from ex
        if dataframe is None:
            raise ReportScheduleCsvFailedError()
        return dataframe

    def _update_query_context(self) -> None:
        """
        Update chart query context.

        To load CSV data from the endpoint the chart must have been saved
        with its query context. For charts without saved query context we
        get a screenshot to force the chart to produce and save the query
        context.
        """
        try:
            self._get_screenshots()
        except (
            ReportScheduleScreenshotFailedError,
            ReportScheduleScreenshotTimeout,
        ) as ex:
            raise ReportScheduleCsvFailedError(
                "Unable to fetch data because the chart has no query context "
                "saved, and an error occurred when fetching it via a screenshot. "
                "Please try loading the chart and saving it again."
            ) from ex

    def _get_log_data(self) -> HeaderDataType:
        chart_id = None
        dashboard_id = None
        report_source = None
        if self._report_schedule.chart:
            report_source = ReportSourceFormat.CHART
            chart_id = self._report_schedule.chart_id
        else:
            report_source = ReportSourceFormat.DASHBOARD
            dashboard_id = self._report_schedule.dashboard_id

        log_data: HeaderDataType = {
            "notification_type": self._report_schedule.type,
            "notification_source": report_source,
            "notification_format": self._report_schedule.report_format,
            "chart_id": chart_id,
            "dashboard_id": dashboard_id,
            "owners": self._report_schedule.owners,
        }
        return log_data

    def _get_notification_content(self) -> NotificationContent:
        """
        Gets a notification content, this is composed by a title and a screenshot

        :raises: ReportScheduleScreenshotFailedError
        """
        # NGLS - BEGIN #
        data = None
        # NGLS - END #
        embedded_data = None
        error_text = None
        screenshot_data = []
        header_data = self._get_log_data()
        url = self._get_url(user_friendly=True)
        if (
            feature_flag_manager.is_feature_enabled("ALERTS_ATTACH_REPORTS")
            or self._report_schedule.type == ReportScheduleType.REPORT
        ):
            logger.info("### _get_notification_content 0")
            if self._report_schedule.report_format == ReportDataFormat.VISUALIZATION:
                screenshot_data = self._get_screenshots()
                if not screenshot_data:
                    error_text = "Unexpected missing screenshot"
            # NGLS - BEGIN #
            elif self._report_schedule.report_format == ReportDataFormat.PDF:
                logger.info("### _get_notification_content 1")
                if self._report_schedule.chart:
                    data = self.get_pdf_data()
                else:
                    data = self.get_pdf_image()
                if not data:
                    error_text = "Unexpected missing PDF file"
            elif self._report_schedule.report_format == ReportDataFormat.DASHBOARD_PDF:
                logger.info("### _get_notification_content 2")
                data = self.get_pdf_image()
                logger.info("### _get_notification_content 2 1")
                if not data:
                    logger.info("### if not data 0")
                    error_text = "Unexpected missing PDF file"
            # NGLS - END #
            elif (
                self._report_schedule.chart
                and self._report_schedule.report_format == ReportDataFormat.DATA
            ):
                data = self._get_csv_data()
                if not data:
                    error_text = "Unexpected missing csv file"
            if error_text:
                logger.info("### error_text 0")
                return NotificationContent(
                    name=self._report_schedule.name,
                    text=error_text,
                    header_data=header_data,
                )

        if (
            self._report_schedule.chart
            and self._report_schedule.report_format == ReportDataFormat.TEXT
        ):
            logger.info("### _get_notification_content 3")
            embedded_data = self._get_embedded_data()

        if self._report_schedule.chart:
            name = (
                f"{self._report_schedule.name}: "
                f"{self._report_schedule.chart.slice_name}"
            )
        else:
            logger.info("### _get_notification_content 4")
            name = (
                f"{self._report_schedule.name}: "
                f"{self._report_schedule.dashboard.dashboard_title}"
            )
        logger.info("### _get_notification_content 5")
        logger.info(screenshot_data) # []
        logger.info(self._report_schedule.description) # None
        logger.info(data) # PDF File
        logger.info(embedded_data) # None
        logger.info(header_data) # {'notification_type': 'Report', 'notification_source': <ReportSourceFormat.DASHBOARD: 'dashboard'>, 'notification_format': 'PDF', 'chart_id': None, 'dashboard_id': 24, 'owners': [Eduardo Sanday]}
        logger.info("### _get_notification_content 6")
        return NotificationContent(
            name=name,
            url=url,
            screenshots=screenshot_data,
            description=self._report_schedule.description,
            # NGLS - BEGIN #
            data=data,
            data_format=self._report_schedule.report_format,
            # NGLS - END #
            embedded_data=embedded_data,
            header_data=header_data,
        )

    def _send(
        self,
        notification_content: NotificationContent,
        recipients: List[ReportRecipients],
    ) -> None:
        """
        Sends a notification to all recipients

        :raises: CommandException
        """
        notification_errors: List[SupersetError] = []
        # logger.info("### _send 0")
        for recipient in recipients:
            # logger.info(recipient.recipient_config_json)
            # logger.info(vars(recipient))
            # logger.info(notification_content)
            notification = create_notification(recipient, notification_content)
            # logger.info("### _send 1")
            try:
                if app.config["ALERT_REPORTS_NOTIFICATION_DRY_RUN"]:
                    logger.info(
                        "Would send notification for alert %s, to %s",
                        self._report_schedule.name,
                        recipient.recipient_config_json,
                    )
                else:
                    # logger.info("### _send 2")
                    notification.send()
                    # logger.info("### _send 3")
            except (NotificationError, SupersetException) as ex:
                # collect errors but keep processing them
                notification_errors.append(
                    SupersetError(
                        message=ex.message,
                        error_type=SupersetErrorType.REPORT_NOTIFICATION_ERROR,
                        level=ErrorLevel.ERROR
                        if ex.status >= 500
                        else ErrorLevel.WARNING,
                    )
                )
        if notification_errors:
            # logger.info("### _send 4")
            # log all errors but raise based on the most severe
            for error in notification_errors:
                logger.warning(str(error))

            if any(error.level == ErrorLevel.ERROR for error in notification_errors):
                raise ReportScheduleSystemErrorsException(errors=notification_errors)
            if any(error.level == ErrorLevel.WARNING for error in notification_errors):
                raise ReportScheduleClientErrorsException(errors=notification_errors)

    def send(self) -> None:
        """
        Creates the notification content and sends them to all recipients

        :raises: CommandException
        """
        # logger.info("### send 0")
        notification_content = self._get_notification_content()
        # logger.info("### send 1")
        self._send(notification_content, self._report_schedule.recipients)

    def send_error(self, name: str, message: str) -> None:
        """
        Creates and sends a notification for an error, to all recipients

        :raises: CommandException
        """
        # logger.info("### send_error 0")
        header_data = self._get_log_data()
        logger.info(
            "header_data in notifications for alerts and reports %s, taskid, %s",
            header_data,
            self._execution_id,
        )
        notification_content = NotificationContent(
            name=name, text=message, header_data=header_data
        )

        # filter recipients to recipients who are also owners
        owner_recipients = [
            ReportRecipients(
                type=ReportRecipientType.EMAIL,
                recipient_config_json=json.dumps({"target": owner.email}),
            )
            for owner in self._report_schedule.owners
        ]

        self._send(notification_content, owner_recipients)

    def is_in_grace_period(self) -> bool:
        """
        Checks if an alert is in it's grace period
        """
        last_success = ReportScheduleDAO.find_last_success_log(
            self._report_schedule, session=self._session
        )
        return (
            last_success is not None
            and self._report_schedule.grace_period
            and datetime.utcnow()
            - timedelta(seconds=self._report_schedule.grace_period)
            < last_success.end_dttm
        )

    def is_in_error_grace_period(self) -> bool:
        """
        Checks if an alert/report on error is in it's notification grace period
        """
        last_success = ReportScheduleDAO.find_last_error_notification(
            self._report_schedule, session=self._session
        )
        if not last_success:
            return False
        return (
            last_success is not None
            and self._report_schedule.grace_period
            and datetime.utcnow()
            - timedelta(seconds=self._report_schedule.grace_period)
            < last_success.end_dttm
        )

    def is_on_working_timeout(self) -> bool:
        """
        Checks if an alert is in a working timeout
        """
        last_working = ReportScheduleDAO.find_last_entered_working_log(
            self._report_schedule, session=self._session
        )
        if not last_working:
            return False
        return (
            self._report_schedule.working_timeout is not None
            and self._report_schedule.last_eval_dttm is not None
            and datetime.utcnow()
            - timedelta(seconds=self._report_schedule.working_timeout)
            > last_working.end_dttm
        )

    def next(self) -> None:
        raise NotImplementedError()


class ReportNotTriggeredErrorState(BaseReportState):
    """
    Handle Not triggered and Error state
    next final states:
    - Not Triggered
    - Success
    - Error
    """

    current_states = [ReportState.NOOP, ReportState.ERROR]
    initial = True

    def next(self) -> None:
        self.update_report_schedule_and_log(ReportState.WORKING)
        try:
            # If it's an alert check if the alert is triggered
            if self._report_schedule.type == ReportScheduleType.ALERT:
                if not AlertCommand(self._report_schedule).run():
                    self.update_report_schedule_and_log(ReportState.NOOP)
                    return
            # logger.info("### send 0 0")
            self.send()
            # logger.info("### send 0 1")
            self.update_report_schedule_and_log(ReportState.SUCCESS)
        except (SupersetErrorsException, Exception) as first_ex:
            error_message = str(first_ex)
            if isinstance(first_ex, SupersetErrorsException):
                error_message = ";".join([error.message for error in first_ex.errors])

            self.update_report_schedule_and_log(
                ReportState.ERROR, error_message=error_message
            )

            # TODO (dpgaspar) convert this logic to a new state eg: ERROR_ON_GRACE
            if not self.is_in_error_grace_period():
                second_error_message = REPORT_SCHEDULE_ERROR_NOTIFICATION_MARKER
                try:
                    # logger.info("### send_error 0 0")
                    self.send_error(
                        f"Error occurred for {self._report_schedule.type}:"
                        f" {self._report_schedule.name}",
                        str(first_ex),
                    )

                except SupersetErrorsException as second_ex:
                    second_error_message = ";".join(
                        [error.message for error in second_ex.errors]
                    )
                except Exception as second_ex:  # pylint: disable=broad-except
                    second_error_message = str(second_ex)
                finally:
                    self.update_report_schedule_and_log(
                        ReportState.ERROR, error_message=second_error_message
                    )
            raise first_ex


class ReportWorkingState(BaseReportState):
    """
    Handle Working state
    next states:
    - Error
    - Working
    """

    current_states = [ReportState.WORKING]

    def next(self) -> None:
        if self.is_on_working_timeout():
            # logger.info("### self.is_on_working_timeout 0")
            exception_timeout = ReportScheduleWorkingTimeoutError()
            self.update_report_schedule_and_log(
                ReportState.ERROR,
                error_message=str(exception_timeout),
            )
            raise exception_timeout
        exception_working = ReportSchedulePreviousWorkingError()
        self.update_report_schedule_and_log(
            ReportState.WORKING,
            error_message=str(exception_working),
        )
        # logger.info("### self.is_on_working_timeout 1")
        raise exception_working


class ReportSuccessState(BaseReportState):
    """
    Handle Success, Grace state
    next states:
    - Grace
    - Not triggered
    - Success
    """

    current_states = [ReportState.SUCCESS, ReportState.GRACE]

    def next(self) -> None:
        if self._report_schedule.type == ReportScheduleType.ALERT:
            if self.is_in_grace_period():
                self.update_report_schedule_and_log(
                    ReportState.GRACE,
                    error_message=str(ReportScheduleAlertGracePeriodError()),
                )
                return
            self.update_report_schedule_and_log(ReportState.WORKING)
            try:
                if not AlertCommand(self._report_schedule).run():
                    self.update_report_schedule_and_log(ReportState.NOOP)
                    return
            except Exception as ex:
                # logger.info("### send_error 0 0 0")
                self.send_error(
                    f"Error occurred for {self._report_schedule.type}:"
                    f" {self._report_schedule.name}",
                    str(ex),
                )
                self.update_report_schedule_and_log(
                    ReportState.ERROR,
                    error_message=REPORT_SCHEDULE_ERROR_NOTIFICATION_MARKER,
                )
                raise ex

        try:
            # logger.info("### next 0")
            self.send()
            self.update_report_schedule_and_log(ReportState.SUCCESS)
        except Exception as ex:  # pylint: disable=broad-except
            self.update_report_schedule_and_log(
                ReportState.ERROR, error_message=str(ex)
            )


class ReportScheduleStateMachine:  # pylint: disable=too-few-public-methods
    """
    Simple state machine for Alerts/Reports states
    """

    states_cls = [ReportWorkingState, ReportNotTriggeredErrorState, ReportSuccessState]

    def __init__(
        self,
        session: Session,
        task_uuid: UUID,
        report_schedule: ReportSchedule,
        scheduled_dttm: datetime,
    ):
        self._session = session
        self._execution_id = task_uuid
        self._report_schedule = report_schedule
        self._scheduled_dttm = scheduled_dttm

    def run(self) -> None:
        state_found = False
        for state_cls in self.states_cls:
            if (self._report_schedule.last_state is None and state_cls.initial) or (
                self._report_schedule.last_state in state_cls.current_states
            ):
                state_cls(
                    self._session,
                    self._report_schedule,
                    self._scheduled_dttm,
                    self._execution_id,
                ).next()
                state_found = True
                break
        if not state_found:
            raise ReportScheduleStateNotFoundError()


class AsyncExecuteReportScheduleCommand(BaseCommand):
    """
    Execute all types of report schedules.
    - On reports takes chart or dashboard screenshots and sends configured notifications
    - On Alerts uses related Command AlertCommand and sends configured notifications
    """

    def __init__(self, task_id: str, model_id: int, scheduled_dttm: datetime):
        self._model_id = model_id
        self._model: Optional[ReportSchedule] = None
        self._scheduled_dttm = scheduled_dttm
        self._execution_id = UUID(task_id)

    def run(self) -> None:
        with session_scope(nullpool=True) as session:
            try:
                self.validate(session=session)
                if not self._model:
                    raise ReportScheduleExecuteUnexpectedError()
                _, username = get_executor(
                    executor_types=app.config["ALERT_REPORTS_EXECUTE_AS"],
                    model=self._model,
                )
                user = security_manager.find_user(username)
                with override_user(user):
                    logger.info(
                        "Running report schedule %s as user %s",
                        self._execution_id,
                        username,
                    )
                    ReportScheduleStateMachine(
                        session, self._execution_id, self._model, self._scheduled_dttm
                    ).run()
            except CommandException as ex:
                raise ex
            except Exception as ex:
                raise ReportScheduleUnexpectedError(str(ex)) from ex

    def validate(  # pylint: disable=arguments-differ
        self, session: Session = None
    ) -> None:
        # Validate/populate model exists
        logger.info(
            "session is validated: id %s, executionid: %s",
            self._model_id,
            self._execution_id,
        )
        self._model = (
            session.query(ReportSchedule).filter_by(id=self._model_id).one_or_none()
        )
        if not self._model:
            raise ReportScheduleNotFoundError()
