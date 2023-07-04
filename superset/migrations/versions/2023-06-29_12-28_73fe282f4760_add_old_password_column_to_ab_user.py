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
"""add_old_password_column_to_ab_user

Revision ID: 73fe282f4760
Revises: f3c2d8ec8595
Create Date: 2023-06-29 12:28:19.454441

"""

# revision identifiers, used by Alembic.
revision = '73fe282f4760'
down_revision = 'f3c2d8ec8595'

from alembic import op
import sqlalchemy as sa
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection

def column_verification(table, column):
    config = op.get_context().config
    engine = engine_from_config(
        config.get_section(config.config_ini_section), prefix='sqlalchemy.')
    inspector = reflection.Inspector.from_engine(engine)
    has_column = False
    for col in inspector.get_columns(table):
        if column not in col['name']:
            continue
        has_column = True
    return has_column

def upgrade():
    with op.batch_alter_table("ab_user") as batch_op:
        if not column_verification("ab_user", "password_history"):
            batch_op.add_column(sa.Column("password_history", sa.String(256), nullable=True))

def downgrade():
    with op.batch_alter_table("ab_user") as batch_op:
        batch_op.drop_column("password_history")