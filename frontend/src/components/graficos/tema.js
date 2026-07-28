/**
 * Tema compartido de los gráficos.
 *
 * Los colores de las series NO son los mismos que los del texto de KPIs. El verde
 * y el rojo del brief (#10B981 / #EF4444) se ven bien como texto etiquetado, pero
 * como barras contiguas quedan por debajo del umbral de separación para daltonismo
 * deuteranope. Los pares de aquí están validados contra el fondo real (#1A1D27):
 *
 *   #199e70 ↔ #e66767 → ΔE 6.5 (protan), 27.5 (visión normal), contraste > 3:1
 *
 * Ese ΔE está en la banda que exige *codificación secundaria*, que sí tenemos:
 * leyenda siempre visible, orden fijo de las series, tooltip con el nombre de cada
 * una, y la tabla de movimientos como vista alternativa.
 */

export const COLORES = {
  ingreso: '#199e70',
  gasto: '#e66767',
  acento: '#818cf8',
  acentoFuerte: '#6366f1',
  // Serie principal + media móvil de la curva de tendencia.
  // Par validado: ΔE 30.1 (protan) / 31.4 (visión normal), ambos > 3:1 de contraste.
  serie: '#6d7ff5',
  media: '#c98500',
  // Chrome del gráfico
  grilla: '#2c3040',
  eje: '#383d4d',
  tintaSuave: '#94a3b8',
  superficie: '#1a1d27',
}

/** Colores del texto de KPIs: los del brief, siempre acompañados de su etiqueta. */
export const COLORES_KPI = {
  ingreso: '#10b981',
  gasto: '#ef4444',
}

export const ejeComun = {
  stroke: COLORES.eje,
  tick: { fill: COLORES.tintaSuave, fontSize: 12 },
  tickLine: false,
  axisLine: false,
}

export const estiloTooltip = {
  contentStyle: {
    background: '#12141c',
    border: '1px solid rgba(255,255,255,0.12)',
    borderRadius: '12px',
    fontSize: '13px',
    padding: '10px 12px',
  },
  labelStyle: { color: '#f8fafc', fontWeight: 600, marginBottom: 4 },
  itemStyle: { color: '#cbd5e1' },
  cursor: { fill: 'rgba(255,255,255,0.04)' },
}
