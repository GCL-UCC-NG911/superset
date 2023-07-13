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
from __future__ import annotations

import json
import logging
from io import BytesIO
from typing import Any, cast, Optional, TYPE_CHECKING, Union

from flask import current_app
from flask_appbuilder.security.sqla.models import User

from superset import security_manager
from superset.thumbnails.digest import get_chart_digest

# from superset.models.slice import Slice
from superset.utils.hashing import md5_sha_from_dict
from superset.utils.urls import modify_url_query
from superset.utils.webdriver import (
    ChartStandaloneMode,
    DashboardStandaloneMode,
    WebDriverProxy,
    WindowSize,
)
from superset.utils.urls import get_url_path

# from superset.charts.data.commands.get_data_command import ChartDataCommand
# from superset.charts.schemas import ChartDataQueryContextSchema

# if TYPE_CHECKING:
    # from superset.common.query_context import QueryContext

logger = logging.getLogger(__name__)

try:
    from PIL import Image
except ModuleNotFoundError:
    logger.info("No PIL installation found")

if TYPE_CHECKING:
    from flask_appbuilder.security.sqla.models import User
    from flask_caching import Cache


class BaseScreenshot:
    driver_type = current_app.config["WEBDRIVER_TYPE"]
    thumbnail_type: str = ""
    element: str = ""
    window_size: WindowSize = (800, 600)
    thumb_size: WindowSize = (400, 300)

    def __init__(self, url: str, digest: str):
        self.digest: str = digest
        self.url = url
        self.screenshot: Optional[bytes] = None

    def driver(self, window_size: Optional[WindowSize] = None) -> WebDriverProxy:
        window_size = window_size or self.window_size
        return WebDriverProxy(self.driver_type, window_size)

    def cache_key(
        self,
        window_size: Optional[Union[bool, WindowSize]] = None,
        thumb_size: Optional[Union[bool, WindowSize]] = None,
    ) -> str:
        window_size = window_size or self.window_size
        thumb_size = thumb_size or self.thumb_size
        args = {
            "thumbnail_type": self.thumbnail_type,
            "digest": self.digest,
            "type": "thumb",
            "window_size": window_size,
            "thumb_size": thumb_size,
        }
        return md5_sha_from_dict(args)

    def get_screenshot(
        self, user: User, window_size: Optional[WindowSize] = None
    ) -> Optional[bytes]:
        driver = self.driver(window_size)
        self.screenshot = driver.get_screenshot(self.url, self.element, user)
        return self.screenshot

    def get(
        self,
        user: User = None,
        cache: Cache = None,
        thumb_size: Optional[WindowSize] = None,
    ) -> Optional[BytesIO]:
        """
            Get thumbnail screenshot has BytesIO from cache or fetch

        :param user: None to use current user or User Model to login and fetch
        :param cache: The cache to use
        :param thumb_size: Override thumbnail site
        """
        payload: Optional[bytes] = None
        cache_key = self.cache_key(self.window_size, thumb_size)
        if cache:
            payload = cache.get(cache_key)
        if not payload:
            payload = self.compute_and_cache(
                user=user, thumb_size=thumb_size, cache=cache
            )
        else:
            logger.info("Loaded thumbnail from cache: %s", cache_key)
        if payload:
            return BytesIO(payload)
        return None

    def get_from_cache(
        self,
        cache: Cache,
        window_size: Optional[WindowSize] = None,
        thumb_size: Optional[WindowSize] = None,
    ) -> Optional[BytesIO]:
        cache_key = self.cache_key(window_size, thumb_size)
        return self.get_from_cache_key(cache, cache_key)

    @staticmethod
    def get_from_cache_key(cache: Cache, cache_key: str) -> Optional[BytesIO]:
        logger.info("Attempting to get from cache: %s", cache_key)
        payload = cache.get(cache_key)
        if payload:
            return BytesIO(payload)
        logger.info("Failed at getting from cache: %s", cache_key)
        return None

    def compute_and_cache(  # pylint: disable=too-many-arguments
        self,
        user: User = None,
        window_size: Optional[WindowSize] = None,
        thumb_size: Optional[WindowSize] = None,
        cache: Cache = None,
        force: bool = True,
    ) -> Optional[bytes]:
        """
        Fetches the screenshot, computes the thumbnail and caches the result

        :param user: If no user is given will use the current context
        :param cache: The cache to keep the thumbnail payload
        :param window_size: The window size from which will process the thumb
        :param thumb_size: The final thumbnail size
        :param force: Will force the computation even if it's already cached
        :return: Image payload
        """
        cache_key = self.cache_key(window_size, thumb_size)
        window_size = window_size or self.window_size
        thumb_size = thumb_size or self.thumb_size
        if not force and cache and cache.get(cache_key):
            logger.info("Thumb already cached, skipping...")
            return None
        logger.info("Processing url for thumbnail: %s", cache_key)

        payload = None

        # Assuming all sorts of things can go wrong with Selenium
        try:
            payload = self.get_screenshot(user=user, window_size=window_size)
        except Exception as ex:  # pylint: disable=broad-except
            logger.warning("Failed at generating thumbnail %s", ex, exc_info=True)

        if payload and window_size != thumb_size:
            try:
                payload = self.resize_image(payload, thumb_size=thumb_size)
            except Exception as ex:  # pylint: disable=broad-except
                logger.warning("Failed at resizing thumbnail %s", ex, exc_info=True)
                payload = None

        if payload:
            logger.info("Caching thumbnail: %s", cache_key)
            cache.set(cache_key, payload)
            logger.info("Done caching thumbnail")
        return payload

    @classmethod
    def resize_image(
        cls,
        img_bytes: bytes,
        output: str = "png",
        thumb_size: Optional[WindowSize] = None,
        crop: bool = True,
    ) -> bytes:
        thumb_size = thumb_size or cls.thumb_size
        img = Image.open(BytesIO(img_bytes))
        logger.debug("Selenium image size: %s", str(img.size))
        if crop and img.size[1] != cls.window_size[1]:
            desired_ratio = float(cls.window_size[1]) / cls.window_size[0]
            desired_width = int(img.size[0] * desired_ratio)
            logger.debug("Cropping to: %s*%s", str(img.size[0]), str(desired_width))
            img = img.crop((0, 0, img.size[0], desired_width))
        logger.debug("Resizing to %s", str(thumb_size))
        img = img.resize(thumb_size, Image.ANTIALIAS)
        new_img = BytesIO()
        if output != "png":
            img = img.convert("RGB")
        img.save(new_img, output)
        new_img.seek(0)
        return new_img.read()

class BaseChartScreenshot:
    # current_user, json_body
    driver_type = current_app.config["WEBDRIVER_TYPE"]
    thumbnail_type: str = ""
    element: str = "standalone"
    window_size: WindowSize = (800, 600)
    thumb_size: WindowSize = (400, 300)

    def __init__(self, user: str, json: any, format: str, pk: int,):
        self.user: str = user
        self.json = json
        self.pk = pk
        self.digest: str = ""
        self.result_format = format

        self.screenshot: Optional[bytes] = None

    def driver2(self, window_size: Optional[WindowSize] = None) -> WebDriverProxy:
        window_size = window_size or self.window_size
        return WebDriverProxy(self.driver_type, window_size)

    def cache_key2(
        self,
        window_size: Optional[Union[bool, WindowSize]] = None,
        thumb_size: Optional[Union[bool, WindowSize]] = None,
    ) -> str:
        window_size = window_size or self.window_size
        thumb_size = thumb_size or self.thumb_size
        args = {
            "thumbnail_type": self.thumbnail_type,
            "digest": self.digest,
            "type": "thumb",
            "window_size": window_size,
            "thumb_size": thumb_size,
        }
        return md5_sha_from_dict(args)
    
    def get_screenshot2(
        self, user: User, window_size: Optional[WindowSize] = None
    ) -> Optional[bytes]:
        driver = self.driver(window_size)
        self.screenshot = driver.get_screenshot(self.url, self.element, user)
        return self.screenshot

    def get_url2(
        self,
        chartId: int,
        user_friendly: bool = False,
        **kwargs: Any,
    ) -> str:
        """
            Get the url for chart report
        """
        force = "true" # if self.json.get("force") else "false"

        return get_url_path(
            "ExploreView.root",
            user_friendly=user_friendly,
            form_data=chartId,
            force=force,
            **kwargs,
        )

    # pylint: disable=no-self-use
    # def _create_query_context_from_form(
    #     self, form_data: Dict[str, Any]
    # ) -> QueryContext:
        # try:
            # return ChartDataQueryContextSchema().load(form_data)
        # except KeyError as ex:
            # raise ValidationError("Request is incorrect") from ex
        # except ValidationError as error:
            # raise error

    def get2(
        self,
        user: User = None,
        cache: Cache = None,
        thumb_size: Optional[WindowSize] = None,
    ) -> Optional[BytesIO]:
        """
            Get thumbnail screenshot has BytesIO from cache or fetch

        :param user: None to use current user or User Model to login and fetch
        :param cache: The cache to use
        :param thumb_size: Override thumbnail site
        """
        # user = security_manager.find_user("admin")
        logger.info("# get - user [%s], cache [%s], thumb_size [%s]", str(self.user), str(cache), str(thumb_size))
        images = []
        for element in self.json.get("formData"):
            logger.info(element)
            if element.get("type") == "CHART":
                url = self.get_url2(chartId=element.get("chartId"))
                logger.info(url)
                # url = 'https://ngls-nginx:8444/explore/?form_data=%7B%22slice_id%22%3A%20339%7D&force=false&standalone=true'
                # url = 'https://ngls-nginx:8444/explore/?form_data=%7B%22slice_id%22%3A%20398%7D&force=false&standalone=true'
                # logger.info(url)
                # chart = Slice(**kwargs)
                # user: Optional[User] = None
                # if has_current_user:
                user = security_manager.find_user(self.user)
                # pylint: disable=import-outside-toplevel,too-many-locals
                # Late import to avoid circular import issues
                from superset.charts.dao import ChartDAO

                chart = ChartDAO.find_by_id(element.get("chartId"), skip_base_filter=True)
                # logger.info(user)
                # chart = cast(Slice, Slice.get(element.get("chartId")))
                # url = get_url_path("Superset.slice", slice_id=element.get("chartId"))
                # logger.info(url)
                # logger.info(chart)
                # query_context = self._create_query_context_from_form(json_body)
                # command = ChartDataCommand(query_context)
                # command.validate()
                logger.info("chartDigest")
                chartDigest = get_chart_digest(chart=chart)
                logger.info(chartDigest)
                screenshot = ChartScreenshot(
                    url,
                    chartDigest,
                    self.window_size,
                    self.thumb_size,
                )
                snapshots = screenshot.get_screenshot(user=user)

                if self.result_format == "image":
                    images.append(snapshots)

                # Convert to image pdf
                if self.result_format == "pdf":
                    for snap in snapshots:
                        img_to_pdf = Image.open(BytesIO(snap))
                        if img_to_pdf.mode == "RGBA":
                            img_to_pdf = img_to_pdf.convert("RGB")
                        images.append(img_to_pdf)

                # screenshot = ChartScreenshot(url, chart.digest)
                # screenshot.compute_and_cache(
                    # user=self.user,
                    # cache=thumbnail_cache,
                    # force=self.force,
                    # window_size=self.window_size,
                    # thumb_size=self.thumb_size,
                # )
                # try:
                    # image = screenshot.get_screenshot(user=user)
                # except SoftTimeLimitExceeded as ex:
                    # logger.warning("A timeout occurred while taking a screenshot.")
                # except Exception as ex:
                    # logger.warning("A exception occurred while taking a screenshot. %s", str(ex))
                # if not image:
                    # logger.warning("Snapshot empty.")
                # if image:
                    # logger.info("return image")
                    # return BytesIO(image)
        if images:
            logger.info("return images")
            if self.result_format == "pdf": 
                new_pdf = BytesIO()
                images[0].save(new_pdf, "PDF", save_all=True, append_images=images[1:])
                new_pdf.seek(0)
                return new_pdf

            return images
        logger.info("# end get")
                

        # payload: Optional[bytes] = None
        # cache_key = self.cache_key(self.window_size, thumb_size)
        # if cache:
            # payload = cache.get(cache_key)
        # if not payload:
            # payload = self.compute_and_cache(
                # user=user, thumb_size=thumb_size, cache=cache
            # )
        # else:
            # logger.info("### Loaded thumbnail from cache: %s", cache_key)
        # if payload:
            # logger.info("### Loaded thumbnail from cache: %s", cache_key)
            # return BytesIO(payload)
        return None

    def get_from_cache2(
        self,
        cache: Cache,
        window_size: Optional[WindowSize] = None,
        thumb_size: Optional[WindowSize] = None,
    ) -> Optional[BytesIO]:
        cache_key = self.cache_key(window_size, thumb_size)
        return self.get_from_cache_key(cache, cache_key)

    @staticmethod
    def get_from_cache_key2(cache: Cache, cache_key: str) -> Optional[BytesIO]:
        logger.info("Attempting to get from cache: %s", cache_key)
        payload = cache.get(cache_key)
        if payload:
            return BytesIO(payload)
        logger.info("Failed at getting from cache: %s", cache_key)
        return None

    def compute_and_cache2(  # pylint: disable=too-many-arguments
        self,
        user: User = None,
        window_size: Optional[WindowSize] = None,
        thumb_size: Optional[WindowSize] = None,
        cache: Cache = None,
        force: bool = True,
    ) -> Optional[bytes]:
        """
        Fetches the screenshot, computes the thumbnail and caches the result

        :param user: If no user is given will use the current context
        :param cache: The cache to keep the thumbnail payload
        :param window_size: The window size from which will process the thumb
        :param thumb_size: The final thumbnail size
        :param force: Will force the computation even if it's already cached
        :return: Image payload
        """
        cache_key = self.cache_key(window_size, thumb_size)
        window_size = window_size or self.window_size
        thumb_size = thumb_size or self.thumb_size
        if not force and cache and cache.get(cache_key):
            logger.info("Thumb already cached, skipping...")
            return None
        logger.info("Processing url for thumbnail: %s", cache_key)

        payload = None

        # Assuming all sorts of things can go wrong with Selenium
        try:
            payload = self.get_screenshot2(user=user, window_size=window_size)
        except Exception as ex:  # pylint: disable=broad-except
            logger.warning("Failed at generating thumbnail %s", ex, exc_info=True)

        if payload and window_size != thumb_size:
            try:
                payload = self.resize_image(payload, thumb_size=thumb_size)
            except Exception as ex:  # pylint: disable=broad-except
                logger.warning("Failed at resizing thumbnail %s", ex, exc_info=True)
                payload = None

        if payload:
            logger.info("Caching thumbnail: %s", cache_key)
            cache.set(cache_key, payload)
            logger.info("Done caching thumbnail")
        return payload

    @classmethod
    def resize_image2(
        cls,
        img_bytes: bytes,
        output: str = "png",
        thumb_size: Optional[WindowSize] = None,
        crop: bool = True,
    ) -> bytes:
        thumb_size = thumb_size or cls.thumb_size
        img = Image.open(BytesIO(img_bytes))
        logger.debug("Selenium image size: %s", str(img.size))
        if crop and img.size[1] != cls.window_size[1]:
            desired_ratio = float(cls.window_size[1]) / cls.window_size[0]
            desired_width = int(img.size[0] * desired_ratio)
            logger.debug("Cropping to: %s*%s", str(img.size[0]), str(desired_width))
            img = img.crop((0, 0, img.size[0], desired_width))
        logger.debug("Resizing to %s", str(thumb_size))
        img = img.resize(thumb_size, Image.ANTIALIAS)
        new_img = BytesIO()
        if output != "png":
            img = img.convert("RGB")
        img.save(new_img, output)
        new_img.seek(0)
        return new_img.read()

    def print2(self):
        logger.info("commit 150")
        logger.info("##### User: [%s], json: [%s], pk: [%s], digest: [%s]", str(self.user), str(self.json), str(self.pk), str(self.digest))
        # logger.info(self.json)
        # logger.info(self.json.url)
        # logger.info(self.json.headers)
        # logger.info(self.json.is_json) # false
        # logger.info(self.json.data) # b''
        # ImmutableMultiDict(
        # [
        # (
        # 'form_data', 
        # '{
        # "formData":
        # [
        # {"dashboardId":142,"dashboardTitle":"[ untitled dashboard ]","type":"DASHBOARD"},
        # {"chartId":339,"sliceName":"Abandoned calls - Table new","uuid":"e9e8d759-aed0-455a-8b92-65c61843e477","height":50,"width":12,"type":"CHART"}
        # ],
        # "force":false,
        # "result_format":"pdf",
        # "result_type":"full"
        # }'
        # ), 
        # (
        # 'csrf_token', 'ImI0MTg3Mzg3NDFkNGViOWFkOWUwNTgzODFkODQ5ZDA5YmYzMzBjMDAi.ZK6EJA.4_c43UrOdw393PsR5scyd3qt5zo'
        # )
        # ]
        # )
        # logger.info(self.json.form)
        # logger.info(self.json.form['form_data'])
        # jsonObject = json.loads(self.json.form['form_data'])
        # logger.info(jsonObject)
        # [
        # {'dashboardId': 142, 'dashboardTitle': '[ untitled dashboard ]', 'type': 'DASHBOARD'},
        # {'chartId': 339, 'sliceName': 'Abandoned calls - Table new', 'uuid': 'e9e8d759-aed0-455a-8b92-65c61843e477', 'height': 50, 'width': 12, 'type': 'CHART'}
        # ]
        # logger.info(jsonObject.get('formData'))
        #logger.info(self.json.form['csrf_token'])

class ChartScreenshot(BaseScreenshot):
    thumbnail_type: str = "chart"
    element: str = "chart-container"

    def __init__(
        self,
        url: str,
        digest: str,
        window_size: Optional[WindowSize] = None,
        thumb_size: Optional[WindowSize] = None,
    ):
        # Chart reports are in standalone="true" mode
        url = modify_url_query(
            url,
            standalone=ChartStandaloneMode.HIDE_NAV.value,
        )
        super().__init__(url, digest)
        self.window_size = window_size or (1600, 1200)
        self.thumb_size = thumb_size or (800, 600)

class DashboardChartScreenshot(BaseChartScreenshot):
    thumbnail_type: str = "chart"
    element: str = "chart-container"

    def __init__(
        self,
        user: str,
        json: any,
        format: str,
        pk: int,
        window_size: Optional[WindowSize] = None,
        thumb_size: Optional[WindowSize] = None,
    ):
        # Chart reports are in standalone="true" mode
        super().__init__(user, json, format, pk)
        self.window_size = window_size or (800, 600)
        self.thumb_size = thumb_size or (800, 600)

class DashboardScreenshot(BaseScreenshot):
    thumbnail_type: str = "dashboard"
    element: str = "standalone"

    def __init__(
        self,
        url: str,
        digest: str,
        window_size: Optional[WindowSize] = None,
        thumb_size: Optional[WindowSize] = None,
    ):
        # per the element above, dashboard screenshots
        # should always capture in standalone
        url = modify_url_query(
            url,
            standalone=DashboardStandaloneMode.REPORT.value,
        )

        super().__init__(url, digest)
        self.window_size = window_size or (1600, 1200)
        self.thumb_size = thumb_size or (800, 600)
