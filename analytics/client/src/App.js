import React, { useReducer, useEffect } from 'react';
import { gql, useQuery } from "@apollo/client";
import { format, addDays, differenceInDays } from 'date-fns';

import {Client as Styletron} from 'styletron-engine-atomic';
import {Provider as StyletronProvider} from 'styletron-react';
import {LightTheme, BaseProvider} from 'baseui';
import {Layer} from 'baseui/layer';
import {StyledSpinnerNext as Spinner} from 'baseui/spinner';
import { useTranslation } from 'react-i18next';

import i18n from './common/i18n';
import { TransportModeShareMap, POIMap } from './Map';
import Controls from './Controls';
import { useAnalyticsData } from './data';
import {userChoiceReducer, initializeUserChoiceState} from './userChoiceReducer';
import { OriginDestinationMatrix, TransportModesPlot } from './Plots';
import preprocessTransportModes from './transportModes';


// Use the symbol to prevent esbuild from tree-shaking it out
if (!i18n.hasLoadedNamespace()) {
  throw new Error('i18n has not loaded')
}

const engine = new Styletron();


const GET_AREAS = gql`
  query getAreas($language: String!) @locale(lang:$language) {
    analytics {
      areaTypes {
        id
        topojsonUrl
        geojsonUrl
        identifier
        name
        dailyTripsDateRange
        dailyLengthsDateRange
        isPoi
        areas {
          id
          identifier
          name
        }
      }
    }
    transportModes {
      id
      identifier
      name
    }
  }
`;

export function MocafAnalytics({ transportModes, areaTypes }) {
  const administrativeAreaTypes = areaTypes.filter(areaType => !areaType.isPoi);
  const [userChoiceState, dispatch] = useReducer(
    userChoiceReducer, ['tre:tilastoalue', administrativeAreaTypes], initializeUserChoiceState);
  const poiAreaTypes = areaTypes.filter(areaType => areaType.isPoi);
  const poiType = poiAreaTypes[0];
  const areaType = administrativeAreaTypes.filter((areaType) => areaType.identifier == userChoiceState.areaType)[0];
  const selectedTransportMode = transportModes.filter((mode) => mode.identifier === userChoiceState.transportMode)[0];
  const start = userChoiceState.dateRange.range[0];
  const end = addDays(userChoiceState.dateRange.range[1], 1)
  const rangeLength = differenceInDays(end, start);
  const areaData = useAnalyticsData({
    type: userChoiceState.analyticsQuantity,
    areaTypeId: areaType.id,
    poiTypeId: poiType.id,
    weekend: userChoiceState.weekSubset,
    startDate: format(start, 'yyyy-MM-dd'),
    endDate: format(end, 'yyyy-MM-dd'),
    transportModes,
  });

  let visComponent;
  if (userChoiceState.visualisation === 'choropleth-map') {
    if (userChoiceState.analyticsQuantity === 'lengths') {
      visComponent = (
        <TransportModeShareMap
          areaType={areaType}
          areaData={areaData}
          selectedTransportMode={selectedTransportMode}
          transportModes={transportModes}
          rangeLength={rangeLength}
        />
      );
    } else {
      visComponent = (
        <POIMap
          poiType={poiType}
          areaType={areaType}
          areaData={areaData}
          selectedTransportMode={selectedTransportMode}
          transportModes={transportModes} />
      )
    }
  } else if (userChoiceState.visualisation === 'table') {
    if (userChoiceState.analyticsQuantity === 'lengths') {
      visComponent = (
        <TransportModesPlot
          areaType={areaType}
          areaData={areaData}
          selectedTransportMode={selectedTransportMode}
          transportModes={transportModes}
          rangeLength={rangeLength}
        />
      );
    } else {
      visComponent = <OriginDestinationMatrix transportModes={transportModes} areaType={areaType} areaData={areaData} mode={selectedTransportMode} />
    }
  }

  return (
    <div style={{display: 'flex', height: '100vh'}}>
      <Layer>
        <Controls userChoices={[userChoiceState, dispatch]}
                  dynamicOptions={{transportModes, areaTypes}}
        />
      </Layer>
      <div style={{width: '100vw', height: '100vh', paddingTop: '180px'}}>
          {visComponent}
    </div>
  </div>
)
}

export function App() {
  const { t, i18n } = useTranslation();
  const { loading, error, data } = useQuery(GET_AREAS, {variables: {language: i18n.language}});

  let mainComponent;
  if (error) {
    mainComponent = <div>{t('error-graphql')}: {error}</div>;
  } else if (loading) {
    mainComponent = <Spinner />;
  } else {
    mainComponent = <MocafAnalytics
                      transportModes={preprocessTransportModes(data.transportModes, i18n.language)}
                      areaTypes={data.analytics.areaTypes} />
  }
  return (
    <StyletronProvider value={engine}>
      <BaseProvider theme={LightTheme}>
        {mainComponent}
      </BaseProvider>
    </StyletronProvider>
  );
}
