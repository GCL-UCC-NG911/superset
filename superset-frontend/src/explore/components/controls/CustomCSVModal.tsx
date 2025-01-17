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
import React, { useCallback, ReactChild, useState } from 'react';
import Modal from 'src/components/Modal';
import Button from 'src/components/Button';
import { css, t, useTheme } from '@superset-ui/core';

const CustomCSVModalTrigger = ({
  latestQueryFormData,
  triggerNode,
  modalTitle,
}: {
  latestQueryFormData: any;
  triggerNode: ReactChild;
  modalTitle: ReactChild;
}) => {
  const [filename, setFilename] = useState<string>('');
  const [showModal, setShowModal] = useState(false);
  const openModal = useCallback(() => setShowModal(true), []);
  const closeModal = useCallback(() => setShowModal(false), []);
  const theme = useTheme();

  const fetchQueryResults = async () => {
    const response = await fetch('/api/v1/chart/data', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        body: JSON.stringify(latestQueryFormData),
      },
    });
    const result = await response.json();
    return result.result[0].data;
  };

  const formatDataAsCSV = (data: any) => {
    if (!Array.isArray(data) || data.length === 0) {
      return '';
    }
    const headers = Object.keys(data[0].join(','));
    const rows = data.map(row =>
      Object.values(row)
        // eslint-disable-next-line prettier/prettier
        .map((value) => (typeof value === 'string' ? `'${value}` : value))
        .join(','),
    );
    return [headers, ...rows].join('\n');
  };

  const downloadCSV = (data: BlobPart, customFilename: any) => {
    const blob = new Blob([data], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);

    link.href = url;
    link.setAttribute('download', `${customFilename}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFilename(e.target.value);
  };

  const handleExport = async () => {
    const data = await fetchQueryResults();
    const csvData = formatDataAsCSV(data);

    const sanitizedFilename = filename.trim() || 'custom_report_test';
    downloadCSV(csvData, sanitizedFilename);
  };

  return (
    <>
      <span
        data-test="span-modal-trigger"
        onClick={openModal}
        role="button"
        tabIndex={0}
      >
        {triggerNode}
      </span>
      {(() => (
        <Modal
          css={css`
            .ant-modal-body {
              display: flex;
              flex-direction: column;
            }
          `}
          show={showModal}
          onHide={closeModal}
          title={modalTitle}
          footer={
            <>
              <Button
                buttonStyle="primary"
                buttonSize="small"
                onClick={handleExport}
              >
                {t('Download chart')}
              </Button>
              <Button
                buttonStyle="primary"
                buttonSize="small"
                onClick={closeModal}
              >
                {t('Close')}
              </Button>
            </>
          }
          responsive
          resizable
          resizableConfig={{
            minHeight: theme.gridUnit * 128,
            minWidth: theme.gridUnit * 128,
            defaultSize: {
              width: 'auto',
              height: 'auto',
            },
          }}
          draggable
          destroyOnClose
        >
          <input
            className="form-control input-sm"
            type="text"
            value={filename}
            onChange={handleInputChange}
            placeholder="Discrepancy ID"
          />
        </Modal>
      ))()}
    </>
  );
};

export default CustomCSVModalTrigger;
