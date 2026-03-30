import React from 'react';
import { PanelProps } from '@perses-dev/plugin-system';
import { ExamplePanelSpec } from './ExamplePanelTypes';

/**
 * ExamplePanel renders the configured query string and optional unit.
 *
 * This is a minimal display panel used as a scaffolding reference.
 * Replace the body with chart/table rendering as needed.
 */
export function ExamplePanel(props: PanelProps<ExamplePanelSpec>): JSX.Element {
  const { spec } = props;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        padding: '16px',
        fontFamily: 'monospace',
        gap: '8px',
      }}
    >
      <div style={{ fontSize: '14px', color: '#666' }}>Query</div>
      <div
        style={{
          fontSize: '13px',
          background: '#f5f5f5',
          borderRadius: '4px',
          padding: '8px 12px',
          maxWidth: '100%',
          overflowX: 'auto',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-all',
        }}
      >
        {spec.query}
      </div>
      {spec.unit !== undefined && (
        <>
          <div style={{ fontSize: '14px', color: '#666', marginTop: '8px' }}>Unit</div>
          <div style={{ fontSize: '13px' }}>{spec.unit}</div>
        </>
      )}
    </div>
  );
}
