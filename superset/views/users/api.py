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
from flask import g, redirect, Response, request
from flask_appbuilder import ModelRestApi
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder.security.sqla.models import User, Role, PermissionView
from flask_appbuilder.api import expose, safe
from flask_jwt_extended.exceptions import NoAuthorizationError
from sqlalchemy.orm.exc import NoResultFound

from superset import app, is_feature_enabled
from superset.daos.user import UserDAO
from superset.utils.slack import get_user_avatar, SlackClientError
from superset.views.base_api import BaseSupersetApi
from superset.views.users.schemas import UserResponseSchema
from superset.views.utils import bootstrap_user_data

user_response_schema = UserResponseSchema()


class CurrentUserRestApi(BaseSupersetApi):
    """An API to get information about the current user"""

    resource_name = "me"
    openapi_spec_tag = "Current User"
    openapi_spec_component_schemas = (UserResponseSchema,)

    @expose("/", methods=("GET",))
    @safe
    def get_me(self) -> Response:
        """Get the user object corresponding to the agent making the request.
        ---
        get:
          summary: Get the user object
          description: >-
            Gets the user object corresponding to the agent making the request,
            or returns a 401 error if the user is unauthenticated.
          responses:
            200:
              description: The current user
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/UserResponseSchema'
            401:
              $ref: '#/components/responses/401'
        """
        try:
            if g.user is None or g.user.is_anonymous:
                return self.response_401()
        except NoAuthorizationError:
            return self.response_401()

        return self.response(200, result=user_response_schema.dump(g.user))

    @expose("/roles/", methods=("GET",))
    @safe
    def get_my_roles(self) -> Response:
        """Get the user roles corresponding to the agent making the request.
        ---
        get:
          summary: Get the user roles
          description: >-
            Gets the user roles corresponding to the agent making the request,
            or returns a 401 error if the user is unauthenticated.
          responses:
            200:
              description: The current user
              content:
                application/json:
                  schema:
                    type: object
                    properties:
                      result:
                        $ref: '#/components/schemas/UserResponseSchema'
            401:
              $ref: '#/components/responses/401'
        """
        try:
            if g.user is None or g.user.is_anonymous:
                return self.response_401()
        except NoAuthorizationError:
            return self.response_401()
        user = bootstrap_user_data(g.user, include_perms=True)
        return self.response(200, result=user)


class UserRestApi(BaseSupersetApi):
    """An API to get information about users"""

    resource_name = "user"
    openapi_spec_tag = "User"
    openapi_spec_component_schemas = (UserResponseSchema,)

    @expose("/<int:user_id>/avatar.png", methods=("GET",))
    @safe
    def avatar(self, user_id: int) -> Response:
        """Get a redirect to the avatar's URL for the user with the given ID.
        ---
        get:
          summary: Get the user avatar
          description: >-
            Gets the avatar URL for the user with the given ID, or returns a 401 error
            if the user is unauthenticated.
          parameters:
            - in: path
              name: user_id
              required: true
              description: The ID of the user
              schema:
                type: string
          responses:
            301:
              description: A redirect to the user's avatar URL
            401:
              $ref: '#/components/responses/401'
            404:
              $ref: '#/components/responses/404'
        """
        avatar_url = None
        try:
            user = UserDAO.get_by_id(user_id)
        except NoResultFound:
            return self.response_404()

        if not user:
            return self.response_404()

        # fetch from the one-to-one relationship
        if len(user.extra_attributes) > 0:
            avatar_url = user.extra_attributes[0].avatar_url
        slack_token = app.config.get("SLACK_API_TOKEN")
        if (
            not avatar_url
            and slack_token
            and is_feature_enabled("SLACK_ENABLE_AVATARS")
        ):
            try:
                # Fetching the avatar url from slack
                avatar_url = get_user_avatar(user.email)
            except SlackClientError:
                return self.response_404()

            UserDAO.set_avatar_url(user, avatar_url)

        # Return a permanent redirect to the avatar URL
        if avatar_url:
            return redirect(avatar_url, code=301)

        # No avatar found, return a "no-content" response
        return Response(status=204)



def parse_legacy_q():
    q = request.args.get("q")
    if not q:
        return {}

    try:
        return json.loads(q)
    except Exception:
        return {}

class UsersRestApi(ModelRestApi):
    resource_name = "security/users"
    datamodel = SQLAInterface(User)

    class_permission_name = "User"
    method_permission_name = {
        "get_list": "list",
        "get": "show",
    }

    list_columns = [
        "id",
        "username",
        "first_name",
        "last_name",
        "email",
        "active",
        "roles.name",
    ]

    show_columns = list_columns

    search_columns = [
        "username",
        "first_name",
        "last_name",
        "email",
    ]

    order_columns = ["id", "username", "email"]

    page_size = 25
    max_page_size = 1000

    @expose("/", methods=("GET",))
    @safe
    def get_list(self, **kwargs):

        args = parse_legacy_q()

        page = args.get("page", 0)
        page_size = args.get("page_size", self.page_size)

        query = self.datamodel.session.query(User)

        query = self._apply_base_filters(query)

        total = query.count()

        results = (
            query.offset(page * page_size)
            .limit(page_size)
            .all()
        )

        data = [
            {
                "id": u.id,
                "username": u.username,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "email": u.email,
                "active": u.active,
                "roles": [{"name": r.name} for r in u.roles],
            }
            for u in results
        ]

        return self.response(
            200,
            count=total,
            result=data,
        )

class SecurityRolesApi(ModelRestApi):
    resource_name = "security/roles"
    datamodel = SQLAInterface(Role)

    class_permission_name = "Role"

    @expose("/", methods=("GET",))
    @safe
    def get_list(self, **kwargs):
        args = parse_legacy_q()

        page = args.get("page", 0)
        page_size = args.get("page_size", 25)

        query = self.datamodel.session.query(Role)

        total = query.count()

        results = (
            query.offset(page * page_size)
            .limit(page_size)
            .all()
        )

        data = [
            {
                "id": r.id,
                "name": r.name,
            }
            for r in results
        ]

        return self.response(200, count=total, result=data)

class SecurityPermissionResourcesApi(ModelRestApi):
    resource_name = "security/permissions-resources"
    datamodel = SQLAInterface(PermissionView)

    class_permission_name = "PermissionView"

    @expose("/", methods=("GET",))
    @safe
    def get_list(self, **kwargs):
        args = parse_legacy_q()

        page = args.get("page", 0)
        page_size = args.get("page_size", 50)

        query = self.datamodel.session.query(PermissionView)

        total = query.count()

        results = (
            query.offset(page * page_size)
            .limit(page_size)
            .all()
        )

        data = [
            {
                "id": p.id,
                "permission": p.permission.name,
                "view_menu": p.view_menu.name,
            }
            for p in results
        ]

        return self.response(200, count=total, result=data)
    
