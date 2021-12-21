import React, { useEffect, useState } from 'react';

import {Select} from 'baseui/select';
import {Block} from 'baseui/block';
import {FormControl} from 'baseui/form-control';
import {Slider} from 'baseui/slider';
import {format, parseISO, differenceInCalendarMonths, addMonths} from 'date-fns';

const selectionValues = {
  weekSubset: [
    {value: true, label: 'weekends'},
    {value: false, label: 'workdays'},
    {value: null, label: 'all days'}
  ],
  areaType: [
    {value: 'tre:paavo', label: 'Postal code area'},
    {value: 'tre:tilastoalue', label: 'Statistics area'},
    {value: 'tre:suunnittelualue', label: 'Planning area'}
  ],
  analyticsQuantity: [
    {value: 'lengths', label: 'Length'},
    {value: 'trips', label: 'Trips'}
  ],
  visualisation: [
    {value: 'choropleth-map', label: 'Map'},
    {value: 'table', label: 'Table'}
  ]
}

const userChoiceSetAction = (key, value) => ({
  type: 'set',
  key: key,
  payload: value
});


function getSelectedValue(key, userChoiceState) {
  return [
    selectionValues[key].find((d) => (
      d.value === userChoiceState[key]))];
}

function StaticSelectControl ({lookup, label, userChoices: [userChoiceState, dispatch]}) {
  return <Select clearable={false}
            options={selectionValues[lookup]}
            labelKey="label"
            valueKey="value"
            value={getSelectedValue(lookup, userChoiceState)}
            onChange={({value}) => (
              dispatch(userChoiceSetAction(lookup, value[0].value)))}
    />
}


function TransportModeControl (
  {userChoices: [userChoiceState, dispatch], transportModes}) {
  const key = 'transportMode'
  let value = null;
  if (transportModes) {
    value = [transportModes?.find((d) => d.identifier === userChoiceState[key])];
  }
  return <Select clearable={false}
                 options={transportModes || []}
                 disabled={transportModes===undefined}
                 labelKey="name"
                 valueKey="identifier"
                 value={value}
                 onChange={({value}) => (
                   dispatch(userChoiceSetAction(key, value[0].identifier)))}
         />
}

function DateRangeSlider ({label, userChoices: [{dateRange}, dispatch]}) {
  const dateBounds = dateRange.bounds;
  const delta = differenceInCalendarMonths(dateBounds[1], dateBounds[0])
  const currentRange = [
    differenceInCalendarMonths(dateRange.range[0], dateRange.bounds[0]),
    differenceInCalendarMonths(dateRange.range[1], dateRange.bounds[0])];
  const [value, setValue] = useState(currentRange);

  function valueToLabel (value) {
    result = addMonths(dateBounds[0], value);
    return format(result, "M/yyyy");
  }
  function onChange ({value}) {
    value && setValue(value);
  }
  function onFinalChange ({value}) {
    value && dispatch(userChoiceSetAction('dateRange', {
      bounds: dateRange.bounds,
      range: [addMonths(dateBounds[0], value[0]), addMonths(dateBounds[0], value[1])]
    }));
  }
  return (
    <div style={{gridColumn: '1/4'}} >
      <Slider value={value}
              onChange={onChange}

              onFinalChange={onFinalChange}
              label={label}
              min={0}
              max={delta}
              valueToLabel={valueToLabel}
              step={1}
      />
    </div>
  );
}

const Controls = ({userChoices, dynamicOptions}) => (
  <div className='controls'
       style={{
         position: 'fixed',
         top: 20,
         left: '50%',
         transform: 'translateX(-50%)',
         padding: 10,
         display: 'grid',
         gridTemplateColumns: '1fr 1fr 1fr 1fr',
         gap: '4px',
         minWidth: '30%',
         backgroundColor: '#ffffffdd',
         border: `1px solid #eee`,
       }}>
    <StaticSelectControl label='Visualisation' lookup='visualisation' userChoices={userChoices} />
    <StaticSelectControl label='What to visualize' lookup='analyticsQuantity' userChoices={userChoices} />
    <StaticSelectControl label='Days of week' lookup='weekSubset' userChoices={userChoices} />
    <StaticSelectControl label='Area type' lookup='areaType' userChoices={userChoices} />
    <DateRangeSlider label='Date range' userChoices={userChoices} />
    <TransportModeControl
      userChoices={userChoices}
      transportModes={dynamicOptions.transportModes} />
  </div>
);

export default Controls;
