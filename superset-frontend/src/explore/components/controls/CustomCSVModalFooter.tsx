/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import React from 'react';
import { isObject } from 'lodash';
import { t, SupersetClient } from '@superset-ui/core';
import Button from 'src/components/Button';

interface SimpleDataSource {
  id: string;
  columns: string;
  type: string;
}

interface CustomCSVModalFooterProps {
  closeModal?: Function;
  changeDatasource?: Function;
  datasource?: SimpleDataSource;
}

const CLOSE = t('Close');
const EXPORT_CHART = t('Download CSV');

const CustomCSVModalFooter: React.FC<CustomCSVModalFooterProps> = (props: {
  closeModal: () => void;
  changeDatasource: () => void;
  datasource: SimpleDataSource;
}) => {
  const viewInSQLLab = (id: string, type: string, sql: string) => {
    const payload = {
      datasourceKey: `${id}__${type}`,
      sql,
    };
    SupersetClient.postForm('/superset/sqllab/', payload);
  };

  const openSQL = () => {
    const { datasource } = props;
    if (isObject(datasource)) {
      const { id, type, columns } = datasource;
      viewInSQLLab(id, type, columns);
    }
  };
  return (
    <div>
      <Button
        onClick={() => {
          props?.closeModal?.();
          props?.changeDatasource?.();
        }}
      >
        {EXPORT_CHART}
      </Button>
      <Button onClick={() => openSQL()}>{CLOSE}</Button>
      <Button
        buttonStyle="primary"
        onClick={() => {
          props?.closeModal?.();
        }}
      >
        {CLOSE}
      </Button>
    </div>
  );
};

export default CustomCSVModalFooter;
