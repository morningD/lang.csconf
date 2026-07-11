import 'virtual:uno.css'
import 'uno:preflights.css'
import 'uno:default.css'

import { createApp } from 'vue'
import { createHead } from '@unhead/vue/client'
import ECharts from 'vue-echarts'
import { use } from 'echarts/core'
import { SVGRenderer } from 'echarts/renderers'
import { PieChart, LineChart, BarChart, RadarChart, CustomChart, TreemapChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  RadarComponent,
} from 'echarts/components'

use([
  SVGRenderer,
  PieChart,
  LineChart,
  BarChart,
  RadarChart,
  CustomChart,
  TreemapChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  RadarComponent,
])

import App from './App.vue'
import router from './router'
import i18n from './i18n'
import { installPageCounter } from './services/pageCounter'

const app = createApp(App)
const head = createHead()

app.component('v-chart', ECharts)
app.use(head)
app.use(router)
app.use(i18n)
installPageCounter(router)

app.mount('#app')
