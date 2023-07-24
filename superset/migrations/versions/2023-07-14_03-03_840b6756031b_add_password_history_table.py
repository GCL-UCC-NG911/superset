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
"""add_password_history_table

Revision ID: 840b6756031b
Revises: f3c2d8ec8595
Create Date: 2023-07-14 03:03:11.900092

"""

# revision identifiers, used by Alembic.
revision = '73fe282f4760'
down_revision = 'f3c2d8ec8595'

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table(
        "password_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("old_password", sa.String(256), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["ab_user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

def downgrade():
    op.drop_table("password_history")