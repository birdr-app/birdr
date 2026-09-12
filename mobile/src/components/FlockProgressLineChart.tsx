import React, { useMemo, useState } from 'react';
import { LayoutChangeEvent, Pressable, StyleSheet, View } from 'react-native';
import Svg, { Circle, Line, Path, Text as SvgText } from 'react-native-svg';
import { colors } from '../theme';

export const FLOCK_PROGRESS_COLORS = [
  '#8b6419',
  '#1d4e89',
  '#2d6a4f',
  '#9b2226',
  '#6a4c93',
  '#bb3e03',
  '#0a9396',
  '#3d405b',
  '#ca6702',
  '#40916c',
  '#ae2012',
  '#005f73',
];

export type FlockProgressSeries = {
  name: string;
  values: Array<number | null>;
  color: string;
};

type Props = {
  labels: string[];
  series: FlockProgressSeries[];
  min: number;
  max: number;
  reverseY?: boolean;
  spanGaps?: boolean;
  yTitle: string;
  xTitle: string;
  selectedIndex: number | null;
  onSelectIndex: (index: number) => void;
  height?: number;
};

const PAD = { top: 12, right: 10, bottom: 36, left: 36 };

function yAt(value: number, min: number, max: number, plotH: number, reverseY: boolean): number {
  const span = Math.max(max - min, 1);
  const t = (value - min) / span;
  return PAD.top + (reverseY ? t : 1 - t) * plotH;
}

function linePath(
  values: Array<number | null>,
  xs: number[],
  min: number,
  max: number,
  plotH: number,
  reverseY: boolean,
  spanGaps: boolean
): string {
  let d = '';
  let started = false;
  values.forEach((value, i) => {
    if (value == null) {
      if (!spanGaps) started = false;
      return;
    }
    const cmd = started ? 'L' : 'M';
    d += `${cmd}${xs[i]} ${yAt(value, min, max, plotH, reverseY)} `;
    started = true;
  });
  return d.trim();
}

function yTicks(min: number, max: number): number[] {
  const span = max - min;
  if (span <= 0) return [min];
  const steps = Math.min(4, Math.max(1, Math.round(span)));
  const ticks: number[] = [];
  for (let i = 0; i <= steps; i += 1) {
    ticks.push(Math.round((min + (span * i) / steps) * 10) / 10);
  }
  return ticks;
}

export function FlockProgressLineChart({
  labels,
  series,
  min,
  max,
  reverseY = false,
  spanGaps = false,
  yTitle,
  xTitle,
  selectedIndex,
  onSelectIndex,
  height = 220,
}: Props) {
  const [width, setWidth] = useState(0);

  const onLayout = (event: LayoutChangeEvent) => {
    const next = Math.round(event.nativeEvent.layout.width);
    if (next !== width) setWidth(next);
  };

  const plotW = Math.max(width - PAD.left - PAD.right, 1);
  const plotH = height - PAD.top - PAD.bottom;
  const n = Math.max(labels.length, 1);
  const xs = useMemo(
    () => labels.map((_, i) => PAD.left + (n === 1 ? plotW / 2 : (i / (n - 1)) * plotW)),
    [labels, n, plotW]
  );
  const ticks = yTicks(min, max);

  const handlePress = (locationX: number) => {
    if (!xs.length) return;
    let best = 0;
    let bestDist = Infinity;
    xs.forEach((x, i) => {
      const dist = Math.abs(x - locationX);
      if (dist < bestDist) {
        bestDist = dist;
        best = i;
      }
    });
    onSelectIndex(best);
  };

  return (
    <View style={styles.wrap} onLayout={onLayout}>
      {width > 0 ? (
        <>
          <Svg width={width} height={height}>
            {ticks.map((tick) => {
              const y = yAt(tick, min, max, plotH, reverseY);
              return (
                <React.Fragment key={`tick-${tick}`}>
                  <Line
                    x1={PAD.left}
                    y1={y}
                    x2={width - PAD.right}
                    y2={y}
                    stroke={colors.primary[100]}
                    strokeWidth={1}
                  />
                  <SvgText
                    x={PAD.left - 6}
                    y={y + 3}
                    fontSize={10}
                    fill={colors.primary[600]}
                    textAnchor="end"
                  >
                    {Number.isInteger(tick) ? String(tick) : tick.toFixed(1)}
                  </SvgText>
                </React.Fragment>
              );
            })}
            {selectedIndex != null && xs[selectedIndex] != null ? (
              <Line
                x1={xs[selectedIndex]}
                y1={PAD.top}
                x2={xs[selectedIndex]}
                y2={PAD.top + plotH}
                stroke={colors.primary[300]}
                strokeWidth={1.5}
                strokeDasharray="4 4"
              />
            ) : null}
            {series.map((s, si) => {
              const d = linePath(s.values, xs, min, max, plotH, reverseY, spanGaps);
              return d ? (
                <Path
                  key={`line-${si}`}
                  d={d}
                  stroke={s.color}
                  strokeWidth={2}
                  fill="none"
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
              ) : null;
            })}
            {series.map((s, si) =>
              s.values.map((value, i) =>
                value == null ? null : (
                  <Circle
                    key={`pt-${si}-${i}`}
                    cx={xs[i]}
                    cy={yAt(value, min, max, plotH, reverseY)}
                    r={selectedIndex === i ? 5 : 3.5}
                    fill={s.color}
                  />
                )
              )
            )}
            {labels.map((label, i) => (
              <SvgText
                key={`x-${label}-${i}`}
                x={xs[i]}
                y={height - 16}
                fontSize={10}
                fill={colors.primary[600]}
                textAnchor="middle"
              >
                {label}
              </SvgText>
            ))}
            <SvgText
              x={width / 2}
              y={height - 2}
              fontSize={10}
              fill={colors.primary[700]}
              textAnchor="middle"
              fontWeight="700"
            >
              {xTitle}
            </SvgText>
            <SvgText
              x={12}
              y={PAD.top + plotH / 2}
              fontSize={10}
              fill={colors.primary[700]}
              textAnchor="middle"
              fontWeight="700"
              transform={`rotate(-90, 12, ${PAD.top + plotH / 2})`}
            >
              {yTitle}
            </SvgText>
          </Svg>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={(event) => handlePress(event.nativeEvent.locationX)}
            accessibilityRole="adjustable"
            accessibilityLabel={yTitle}
          />
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { width: '100%', minHeight: 220 },
});
