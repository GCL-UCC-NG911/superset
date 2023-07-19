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
import PropTypes from 'prop-types';

import { SupersetClient, t } from '@superset-ui/core';

import { Menu } from 'src/components/Menu';
import { URL_PARAMS } from 'src/constants';
import ShareMenuItems from 'src/dashboard/components/menu/ShareMenuItems';
import CssEditor from 'src/dashboard/components/CssEditor';
import RefreshIntervalModal from 'src/dashboard/components/RefreshIntervalModal';
import SaveModal from 'src/dashboard/components/SaveModal';
import HeaderReportDropdown from 'src/components/ReportModal/HeaderReportDropdown';
import injectCustomCss from 'src/dashboard/util/injectCustomCss';
import { SAVE_TYPE_NEWDASHBOARD } from 'src/dashboard/util/constants';
import FilterScopeModal from 'src/dashboard/components/filterscope/FilterScopeModal';
import downloadAsImage from 'src/utils/downloadAsImage';
/* NGLS - BEGIN */
import downloadAsPdf from 'src/utils/downloadAsPdf';
// import Alert from 'src/components/Alert';
/* NGLS - END */
import getDashboardUrl from 'src/dashboard/util/getDashboardUrl';
import { getActiveFilters } from 'src/dashboard/util/activeDashboardFilters';
import { getUrlParam } from 'src/utils/urlUtils';
import { FILTER_BOX_MIGRATION_STATES } from 'src/explore/constants';
import {
  LOG_ACTIONS_DASHBOARD_DOWNLOAD_AS_IMAGE,
  /* NGLS - BEGIN */
  LOG_ACTIONS_DASHBOARD_DOWNLOAD_AS_PDF,
  /* NGLS - END */
} from 'src/logger/LogUtils';
import { addWarningToast } from 'src/components/MessageToasts/actions';

const propTypes = {
  addSuccessToast: PropTypes.func.isRequired,
  addDangerToast: PropTypes.func.isRequired,
  dashboardInfo: PropTypes.object.isRequired,
  dashboardId: PropTypes.number,
  dashboardTitle: PropTypes.string,
  dataMask: PropTypes.object.isRequired,
  customCss: PropTypes.string,
  colorNamespace: PropTypes.string,
  colorScheme: PropTypes.string,
  onChange: PropTypes.func.isRequired,
  updateCss: PropTypes.func.isRequired,
  forceRefreshAllCharts: PropTypes.func.isRequired,
  downlaodAllChartsAsPdf: PropTypes.func.isRequired,
  refreshFrequency: PropTypes.number,
  shouldPersistRefreshFrequency: PropTypes.bool.isRequired,
  setRefreshFrequency: PropTypes.func.isRequired,
  startPeriodicRender: PropTypes.func.isRequired,
  editMode: PropTypes.bool.isRequired,
  userCanEdit: PropTypes.bool,
  userCanShare: PropTypes.bool,
  userCanSave: PropTypes.bool,
  userCanCurate: PropTypes.bool.isRequired,
  isLoading: PropTypes.bool.isRequired,
  layout: PropTypes.object.isRequired,
  expandedSlices: PropTypes.object,
  onSave: PropTypes.func.isRequired,
  showPropertiesModal: PropTypes.func.isRequired,
  manageEmbedded: PropTypes.func.isRequired,
  logEvent: PropTypes.func,
  refreshLimit: PropTypes.number,
  refreshWarning: PropTypes.string,
  lastModifiedTime: PropTypes.number.isRequired,
  filterboxMigrationState: PropTypes.oneOf(
    Object.keys(FILTER_BOX_MIGRATION_STATES).map(
      key => FILTER_BOX_MIGRATION_STATES[key],
    ),
  ),
};

const defaultProps = {
  colorNamespace: undefined,
  colorScheme: undefined,
  refreshLimit: 0,
  refreshWarning: null,
  filterboxMigrationState: FILTER_BOX_MIGRATION_STATES.NOOP,
};

const MENU_KEYS = {
  SAVE_MODAL: 'save-modal',
  SHARE_DASHBOARD: 'share-dashboard',
  REFRESH_DASHBOARD: 'refresh-dashboard',
  AUTOREFRESH_MODAL: 'autorefresh-modal',
  SET_FILTER_MAPPING: 'set-filter-mapping',
  EDIT_PROPERTIES: 'edit-properties',
  EDIT_CSS: 'edit-css',
  DOWNLOAD_AS_IMAGE: 'download-as-image',
  /* NGLS - BEGIN */
  DOWNLOAD_AS_PDF: 'download-as-pdf',
   DOWNLOAD_CHARTS_DATA_AS_PDF: 'download-charts-data-as-pdf',
  DOWNLOAD_CUSTOM_AS_PDF: 'download-custom-as-pdf',
  DOWNLOAD_SUBMENU: 'download-submenu',
  /* NGLS - END */
  TOGGLE_FULLSCREEN: 'toggle-fullscreen',
  MANAGE_EMBEDDED: 'manage-embedded',
  MANAGE_EMAIL_REPORT: 'manage-email-report',
};

const SCREENSHOT_NODE_SELECTOR = '.dashboard';

/* NGLS - BEGIN */
const buildV1DashboardDataPayload = ({
  formData,
  force,
  resultFormat,
  resultType,
}) => {
  console.log('### buildV1DashboardDataPayload');
  return {
    formData,
    force,
    result_format: resultFormat,
    result_type: resultType,
  };
};
/* NGLS - END */

class HeaderActionsDropdown extends React.PureComponent {
  static discardChanges() {
    window.location.reload();
  }

  constructor(props) {
    super(props);
    this.state = {
      css: props.customCss,
      cssTemplates: [],
      showReportSubMenu: null,
    };

    this.changeCss = this.changeCss.bind(this);
    this.changeRefreshInterval = this.changeRefreshInterval.bind(this);
    this.handleMenuClick = this.handleMenuClick.bind(this);
    this.setShowReportSubMenu = this.setShowReportSubMenu.bind(this);
  }

  downloadPDFTables(
    dashboardId,
    formData,
    resultFormat = 'image',
    resultType = 'full',
    force = false,
  ) {
    const url = `/api/v1/dashboard/${dashboardId}/download`;
    console.log(
      '### exportTables start - resultFormat, resultType, force, ownState, formData',
    );
    console.log(resultFormat);
    console.log(resultType);
    console.log(force);
    console.log(formData);
    console.log(url);
    const payload = buildV1DashboardDataPayload({
      formData,
      force,
      resultFormat,
      resultType,
    });
    console.log(payload);
    // SupersetClient.postForm(url, { form_data: safeStringify(payload) });

    // const querySettings = {
    // url,
    // headers: { 'Content-Type': 'application/json' },
    // body: JSON.stringify(payload),
    // };

    try {
      SupersetClient.postJsonForm(url, { form_data: JSON.stringify(payload) });
    } catch (error) {
      // logging.error(t('Unable to download charts of dashboard'));
      console.error('Unable to download charts of dashboard');
      console.error(error);
    }

    console.log(
      '### exportTables end - resultFormat, resultType, force, ownState, formData',
    );
  }

  getAllTables(props, element) {
    if (props === null || element === null || element === '') {
      return [];
    }

    const childrenElement = props[element];
    if (childrenElement?.type === 'CHART') {
      // console.log('type === CHART');
      return [
        {
          chartId: childrenElement.meta.chartId,
          sliceName: childrenElement.meta.sliceName,
          uuid: childrenElement.meta.uuid,
          height: childrenElement.meta.height,
          width: childrenElement.meta.width,
          type: 'CHART',
        },
      ];
    }
    if (childrenElement?.type === 'MARKDOWN') {
      // console.log('type === MARKDOWN');
      return [
        {
          code: childrenElement.meta.code,
          height: childrenElement.meta.height,
          width: childrenElement.meta.width,
          type: 'MARKDOWN',
        },
      ];
    }
    const alltables = [];
    for (let i = 0; i < childrenElement.children.length; i += 1) {
      const table = this.getAllTables(props, childrenElement.children[i]);
      // console.log(childrenElement.children[i]);
      // console.log(table);
      // console.log(table.length);
      table.forEach(element => {
        alltables.push(element);
      });
    }
    return alltables;
  }

  getAllFilters(defaultFilters, changeFilters = null) {
    if (!defaultFilters) {
      console.log('defaultFilters is empty');
      return [];
    }

    console.log(defaultFilters);
    const allFilters = [];
    defaultFilters.forEach(element => {
      allFilters.push({
        filterId: element.id,
        name: element.name,
        extraFormData: element.defaultDataMask.extraFormData,
        value: element.defaultDataMask.filterState.value,
        filterType: element.filterType,
        type: 'FILTER',
      });
    });

    console.log(changeFilters);
    if (!changeFilters) {
      return allFilters;
    }

    for (let i = 0; i < allFilters.length; i += 1) {
      console.log(allFilters[i].filterId);
      console.log(changeFilters[allFilters[i].filterId]);
      if (changeFilters[allFilters[i].filterId]?.filterState?.value) {
        allFilters[i].value =
          changeFilters[allFilters[i].filterId]?.filterState?.value;
      }
    }

    return allFilters;
  }

  downloadAllCharts(props, type) {
    console.log('commit 118');
    console.log(props);
    // console.log(props.dashboardInfo.metadata.native_filter_configuration);
    // console.log(props.dataMask);
    const allFilters = this.getAllFilters(
      props?.dashboardInfo?.metadata?.native_filter_configuration,
      props?.dataMask,
    );
    console.log(allFilters);
    // console.log(props?.dashboardId);
    // console.log(props?.dashboardTitle);
    // console.log(props?.dashboardInfo);
    // console.log(props?.dashboardInfo?.charts?.length);
    // console.log(props?.dashboardInfo?.position_json);
    const dashboardInfo = [
      {
        dashboardId: props?.dashboardId,
        dashboardTitle: props?.dashboardTitle,
        type: 'DASHBOARD',
      },
    ];
    console.log('### native_filter_configuration');
    props?.dashboardInfo?.metadata?.native_filter_configuration?.forEach(
      element => {
        console.log(element);
        console.log(element?.id);
        console.log(element?.name);
      },
    );
    // console.log('### layout');
    // console.log(JSON.stringify(props?.layout));
    // console.log('### children');
    // const gridChildren = props?.layout?.GRID_ID?.children;
    // console.log(gridChildren.length);
    const allTables = this.getAllTables(props?.layout, 'ROOT_ID');
    console.log('### allTables');
    console.log(allTables);
    allTables.forEach(element => {
      dashboardInfo.push(element);
    });
    allFilters.forEach(element => {
      dashboardInfo.push(element);
    });
    console.log('### dashboardInfo');
    console.log(dashboardInfo);
    this.downloadPDFTables(
      props?.dashboardId,
      dashboardInfo,
      type,
      'full',
      false,
    );
  }

  UNSAFE_componentWillMount() {
    SupersetClient.get({ endpoint: '/csstemplateasyncmodelview/api/read' })
      .then(({ json }) => {
        const cssTemplates = json.result.map(row => ({
          value: row.template_name,
          css: row.css,
          label: row.template_name,
        }));
        this.setState({ cssTemplates });
      })
      .catch(() => {
        this.props.addDangerToast(
          t('An error occurred while fetching available CSS templates'),
        );
      });
  }

  UNSAFE_componentWillReceiveProps(nextProps) {
    if (this.props.customCss !== nextProps.customCss) {
      this.setState({ css: nextProps.customCss }, () => {
        injectCustomCss(nextProps.customCss);
      });
    }
  }

  setShowReportSubMenu(show) {
    this.setState({
      showReportSubMenu: show,
    });
  }

  changeCss(css) {
    this.props.onChange();
    this.props.updateCss(css);
  }

  changeRefreshInterval(refreshInterval, isPersistent) {
    this.props.setRefreshFrequency(refreshInterval, isPersistent);
    this.props.startPeriodicRender(refreshInterval * 1000);
  }

  handleMenuClick({ key, domEvent }) {
    switch (key) {
      case MENU_KEYS.REFRESH_DASHBOARD:
        this.props.forceRefreshAllCharts();
        this.props.addSuccessToast(t('Refreshing charts'));
        break;
      case MENU_KEYS.EDIT_PROPERTIES:
        this.props.showPropertiesModal();
        break;
      case MENU_KEYS.DOWNLOAD_AS_IMAGE: {
        // menu closes with a delay, we need to hide it manually,
        // so that we don't capture it on the screenshot
        const menu = document.querySelector(
          '.ant-dropdown:not(.ant-dropdown-hidden)',
        );
        menu.style.visibility = 'hidden';
        // span a pop up
        // alert("This process take a long time please waiting....");
        // addWarningToast(t('Image download takes a long time, please wait.'));
        downloadAsImage(
          SCREENSHOT_NODE_SELECTOR,
          this.props.dashboardTitle,
          true,
        )(domEvent).then(() => {
          menu.style.visibility = 'visible';
        });

        this.props.logEvent?.(LOG_ACTIONS_DASHBOARD_DOWNLOAD_AS_IMAGE);
        break;
      }
      /* NGLS - BEGIN */
      case MENU_KEYS.DOWNLOAD_AS_PDF: {
        // menu closes with a delay, we need to hide it manually,
        // so that we don't capture it on the screenshot
        const menu = document.querySelector(
          '.ant-dropdown:not(.ant-dropdown-hidden)',
        );
        menu.style.visibility = 'hidden';
        downloadAsPdf(
          SCREENSHOT_NODE_SELECTOR,
          this.props.dashboardTitle,
          true,
        )(domEvent).then(() => {
          menu.style.visibility = 'visible';
        });
        this.props.logEvent?.(LOG_ACTIONS_DASHBOARD_DOWNLOAD_AS_PDF);
        break;
      }
      case MENU_KEYS.DOWNLOAD_CHARTS_DATA_AS_PDF: {
        this.props.downlaodAllChartsAsPdf();
        // this.props.logEvent?.(LOG_ACTIONS_DASHBOARD_DOWNLOAD_CUSTOM_AS_PDF);
        break;
      }
      /* NGLS - END */
      case MENU_KEYS.TOGGLE_FULLSCREEN: {
        const url = getDashboardUrl({
          pathname: window.location.pathname,
          filters: getActiveFilters(),
          hash: window.location.hash,
          standalone: !getUrlParam(URL_PARAMS.standalone),
        });
        window.location.replace(url);
        break;
      }
      case MENU_KEYS.MANAGE_EMBEDDED: {
        this.props.manageEmbedded();
        break;
      }
      default:
        break;
    }
  }

  render() {
    const {
      dashboardTitle,
      dashboardId,
      dashboardInfo,
      refreshFrequency,
      shouldPersistRefreshFrequency,
      editMode,
      customCss,
      colorNamespace,
      colorScheme,
      layout,
      expandedSlices,
      onSave,
      userCanEdit,
      userCanShare,
      userCanSave,
      userCanCurate,
      isLoading,
      refreshLimit,
      refreshWarning,
      lastModifiedTime,
      addSuccessToast,
      addDangerToast,
      filterboxMigrationState,
      setIsDropdownVisible,
      isDropdownVisible,
      ...rest
    } = this.props;

    const emailTitle = t('Superset dashboard');
    const emailSubject = `${emailTitle} ${dashboardTitle}`;
    const emailBody = t('Check out this dashboard: ');

    const url = getDashboardUrl({
      pathname: window.location.pathname,
      filters: getActiveFilters(),
      hash: window.location.hash,
    });

    const refreshIntervalOptions =
      dashboardInfo.common?.conf?.DASHBOARD_AUTO_REFRESH_INTERVALS;

    return (
      <Menu selectable={false} data-test="header-actions-menu" {...rest}>
        {!editMode && (
          <Menu.Item
            key={MENU_KEYS.REFRESH_DASHBOARD}
            data-test="refresh-dashboard-menu-item"
            disabled={isLoading}
            onClick={this.handleMenuClick}
          >
            {t('Refresh dashboard')}
          </Menu.Item>
        )}
        {!editMode && (
          <Menu.Item
            key={MENU_KEYS.TOGGLE_FULLSCREEN}
            onClick={this.handleMenuClick}
          >
            {getUrlParam(URL_PARAMS.standalone)
              ? t('Exit fullscreen')
              : t('Enter fullscreen')}
          </Menu.Item>
        )}
        {editMode && (
          <Menu.Item
            key={MENU_KEYS.EDIT_PROPERTIES}
            onClick={this.handleMenuClick}
          >
            {t('Edit properties')}
          </Menu.Item>
        )}
        {editMode && (
          <Menu.Item key={MENU_KEYS.EDIT_CSS}>
            <CssEditor
              triggerNode={<span>{t('Edit CSS')}</span>}
              initialCss={this.state.css}
              templates={this.state.cssTemplates}
              onChange={this.changeCss}
            />
          </Menu.Item>
        )}
        <Menu.Divider />
        {userCanSave && (
          <Menu.Item key={MENU_KEYS.SAVE_MODAL}>
            <SaveModal
              addSuccessToast={this.props.addSuccessToast}
              addDangerToast={this.props.addDangerToast}
              dashboardId={dashboardId}
              dashboardTitle={dashboardTitle}
              dashboardInfo={dashboardInfo}
              saveType={SAVE_TYPE_NEWDASHBOARD}
              layout={layout}
              expandedSlices={expandedSlices}
              refreshFrequency={refreshFrequency}
              shouldPersistRefreshFrequency={shouldPersistRefreshFrequency}
              lastModifiedTime={lastModifiedTime}
              customCss={customCss}
              colorNamespace={colorNamespace}
              colorScheme={colorScheme}
              onSave={onSave}
              triggerNode={
                <span data-test="save-as-menu-item">{t('Save as')}</span>
              }
              canOverwrite={userCanEdit}
            />
          </Menu.Item>
        )}
        {
          /* NGLS */
          !editMode && (
            <Menu.SubMenu
              title={t('Download')}
              key={MENU_KEYS.DOWNLOAD_SUBMENU}
            >
              <Menu.Item
                key={MENU_KEYS.DOWNLOAD_AS_IMAGE}
                onClick={this.handleMenuClick}
              >
                {t('Screen as image')}
              </Menu.Item>
              <Menu.Item
                key={MENU_KEYS.DOWNLOAD_AS_PDF}
                onClick={this.handleMenuClick}
              >
                {t('Screen as PDF')}
              </Menu.Item>
              <Menu.Item
                key={MENU_KEYS.DOWNLOAD_CHARTS_DATA_AS_PDF}
                onClick={this.handleMenuClick}
              >
                {t('All charts data as PDF')}
              </Menu.Item>
            </Menu.SubMenu>
          )
        }
        {userCanShare && (
          <Menu.SubMenu
            key={MENU_KEYS.SHARE_DASHBOARD}
            data-test="share-dashboard-menu-item"
            disabled={isLoading}
            title={t('Share')}
          >
            <ShareMenuItems
              url={url}
              copyMenuItemTitle={t('Copy permalink to clipboard')}
              emailMenuItemTitle={t('Share permalink by email')}
              emailSubject={emailSubject}
              emailBody={emailBody}
              addSuccessToast={addSuccessToast}
              addDangerToast={addDangerToast}
              dashboardId={dashboardId}
            />
          </Menu.SubMenu>
        )}
        {!editMode && userCanCurate && (
          <Menu.Item
            key={MENU_KEYS.MANAGE_EMBEDDED}
            onClick={this.handleMenuClick}
          >
            {t('Embed dashboard')}
          </Menu.Item>
        )}
        <Menu.Divider />
        {!editMode ? (
          this.state.showReportSubMenu ? (
            <>
              <Menu.SubMenu title={t('Manage email report')}>
                <HeaderReportDropdown
                  dashboardId={dashboardInfo.id}
                  setShowReportSubMenu={this.setShowReportSubMenu}
                  showReportSubMenu={this.state.showReportSubMenu}
                  setIsDropdownVisible={setIsDropdownVisible}
                  isDropdownVisible={isDropdownVisible}
                  useTextMenu
                />
              </Menu.SubMenu>
              <Menu.Divider />
            </>
          ) : (
            <Menu>
              <HeaderReportDropdown
                dashboardId={dashboardInfo.id}
                setShowReportSubMenu={this.setShowReportSubMenu}
                setIsDropdownVisible={setIsDropdownVisible}
                isDropdownVisible={isDropdownVisible}
                useTextMenu
              />
            </Menu>
          )
        ) : null}
        {editMode &&
          filterboxMigrationState !== FILTER_BOX_MIGRATION_STATES.CONVERTED && (
            <Menu.Item key={MENU_KEYS.SET_FILTER_MAPPING}>
              <FilterScopeModal
                className="m-r-5"
                triggerNode={t('Set filter mapping')}
              />
            </Menu.Item>
          )}

        <Menu.Item key={MENU_KEYS.AUTOREFRESH_MODAL}>
          <RefreshIntervalModal
            addSuccessToast={this.props.addSuccessToast}
            refreshFrequency={refreshFrequency}
            refreshLimit={refreshLimit}
            refreshWarning={refreshWarning}
            onChange={this.changeRefreshInterval}
            editMode={editMode}
            refreshIntervalOptions={refreshIntervalOptions}
            triggerNode={<span>{t('Set auto-refresh interval')}</span>}
          />
        </Menu.Item>
      </Menu>
    );
  }
}

HeaderActionsDropdown.propTypes = propTypes;
HeaderActionsDropdown.defaultProps = defaultProps;

export default HeaderActionsDropdown;
