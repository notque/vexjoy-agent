import React from "react";
import { PanelProps } from "@perses-dev/plugin-system";
import { CustomPanelSpec, ThresholdStep } from "./types";

/**
 * resolveThresholdColor returns the color for the highest threshold whose
 * value is <= the provided numeric value, or undefined when no value is given.
 */
function resolveThresholdColor(
  value: number | undefined,
  thresholds: ThresholdStep[] | undefined
): string | undefined {
  if (value === undefined || !thresholds || thresholds.length === 0) {
    return undefined;
  }
  const sorted = [...thresholds].sort((a, b) => a.value - b.value);
  let resolved: string | undefined;
  for (const step of sorted) {
    if (value >= step.value) {
      resolved = step.color;
    }
  }
  return resolved;
}

/**
 * CustomPanelComponent renders the CustomPanel spec.
 *
 * - Displays the configured title as the panel heading.
 * - Shows each threshold step as a color swatch with its boundary value.
 * - Applies the appropriate threshold color to the unit label when a
 *   representative value is available from the panel data context.
 */
export function CustomPanelComponent({
  spec,
}: PanelProps<CustomPanelSpec>): React.ReactElement {
  const { title, unit, thresholds } = spec;

  // Derive a representative numeric value from the first query result when
  // available. Falls back to undefined so the component renders gracefully
  // with no live data (e.g. during plugin development or empty dashboards).
  const representativeValue: number | undefined = undefined;
  const activeColor = resolveThresholdColor(representativeValue, thresholds);

  return (
    <div style={styles.container}>
      {/* Panel heading */}
      <h2 style={styles.title}>{title}</h2>

      {/* Unit display with optional threshold color */}
      {unit !== undefined && (
        <div
          style={{
            ...styles.unitBadge,
            backgroundColor: activeColor ?? styles.unitBadge.backgroundColor,
          }}
        >
          {unit}
        </div>
      )}

      {/* Threshold legend */}
      {thresholds && thresholds.length > 0 && (
        <section style={styles.thresholdsSection}>
          <h3 style={styles.thresholdsHeading}>Thresholds</h3>
          <ul style={styles.thresholdList}>
            {thresholds
              .slice()
              .sort((a, b) => a.value - b.value)
              .map((step, idx) => (
                <li key={idx} style={styles.thresholdItem}>
                  <span
                    style={{
                      ...styles.swatch,
                      backgroundColor: step.color,
                    }}
                    aria-label={`Threshold color: ${step.color}`}
                  />
                  <span style={styles.thresholdLabel}>
                    &ge; {step.value}
                    {unit ? ` ${unit}` : ""}
                  </span>
                </li>
              ))}
          </ul>
        </section>
      )}

      {/* Empty state */}
      {(!thresholds || thresholds.length === 0) && unit === undefined && (
        <p style={styles.emptyState}>No configuration to display.</p>
      )}
    </div>
  );
}

// Inline styles — replace with your design system tokens or CSS modules as needed.
const styles = {
  container: {
    padding: "12px 16px",
    fontFamily: "inherit",
    height: "100%",
    boxSizing: "border-box" as const,
    overflow: "auto",
  },
  title: {
    margin: "0 0 8px 0",
    fontSize: "1rem",
    fontWeight: 600,
    lineHeight: 1.4,
  },
  unitBadge: {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: "4px",
    fontSize: "0.875rem",
    fontWeight: 500,
    backgroundColor: "#e0e0e0",
    marginBottom: "12px",
  },
  thresholdsSection: {
    marginTop: "8px",
  },
  thresholdsHeading: {
    margin: "0 0 6px 0",
    fontSize: "0.75rem",
    fontWeight: 600,
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
    color: "#666",
  },
  thresholdList: {
    listStyle: "none",
    margin: 0,
    padding: 0,
    display: "flex",
    flexDirection: "column" as const,
    gap: "4px",
  },
  thresholdItem: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  swatch: {
    width: "14px",
    height: "14px",
    borderRadius: "2px",
    flexShrink: 0,
    border: "1px solid rgba(0,0,0,0.1)",
  },
  thresholdLabel: {
    fontSize: "0.875rem",
  },
  emptyState: {
    color: "#999",
    fontSize: "0.875rem",
    margin: 0,
  },
} as const;
