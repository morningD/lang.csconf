import 'virtual:uno.css'
import 'uno:preflights.css'
import 'uno:default.css'

import { createApp } from 'vue'
import ECharts from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, LineChart, BarChart, RadarChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  RadarComponent,
} from 'echarts/components'

use([
  CanvasRenderer,
  PieChart,
  LineChart,
  BarChart,
  RadarChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  RadarComponent,
])

import App from './App.vue'
import router from './router'
import i18n from './i18n'

const app = createApp(App)

app.component('v-chart', ECharts)
app.use(router)
app.use(i18n)

app.mount('#app')
