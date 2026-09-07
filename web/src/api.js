// 所有请求都自动带上当前选中的数据集（?dataset=xxx）。
//
// 数据集由 App 顶栏的下拉框切换，切换时调用 `api.selectDataset(name)`，
// 之后本模块内所有请求都会附加该参数 —— 各个 view 不需要感知数据集的存在。
//
// 后端约定（reid_sys/api.py）：所有检索类接口都接受可选的 ?dataset=，
// 不传则用后端当前值（初始为 data/ 下按名字排序的第一个数据集）。

/** 当前选中的数据集名；null 表示「跟随后端默认」。 */
let currentDataset = null

/** 后端已知的数据集列表（/api/datasets），App 启动时拉一次。 */
export function getDataset() {
  return currentDataset
}

export function setDataset(name) {
  currentDataset = name || null
}

/** 给 URL 拼上 ?dataset=（已有 query string 时用 &）。 */
const withDataset = (url) => {
  if (!currentDataset) return url
  const sep = url.includes('?') ? '&' : '?'
  return `${url}${sep}dataset=${encodeURIComponent(currentDataset)}`
}

const json = async (res) => {
  if (!res.ok) throw new Error((await res.text()).slice(0, 400) || res.statusText)
  return res.json()
}

const get = (url) => fetch(withDataset(url)).then(json)
const post = (url, body) => fetch(withDataset(url), { method: 'POST', body }).then(json)
const postJson = (url, data) =>
  fetch(withDataset(url), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then(json)
const upload = (url, file) => {
  const fd = new FormData()
  fd.append('file', file)
  return post(url, fd)
}

export const api = {
  // ---- 数据集注册表 ----
  datasets: () => get('/api/datasets'),
  selectDataset: (name) => {
    setDataset(name)
    return postJson('/api/datasets/select', { name })
  },

  // ---- 检索主链路 ----
  status: () => get('/api/status'),
  probe: () => get('/api/probe'),
  gallery: (offset, limit, q = '') =>
    get(`/api/gallery?offset=${offset}&limit=${limit}&q=${encodeURIComponent(q)}`),
  index: () => post('/api/index'),
  evaluate: () => get('/api/eval'),
  searchProbe: (name, topk) => post(`/api/search/probe?name=${encodeURIComponent(name)}&topk=${topk}`),
  searchUpload: (file, topk) => upload(`/api/search/upload?topk=${topk}`, file),
  detect: (file) => upload('/api/detect', file),
  trackDemo: (persons, frames, interval) =>
    post(`/api/detect/track-demo?persons=${persons}&frames=${frames}&interval=${interval}`),

  // ---- 未接入能力的接口（契约已定义，服务尚未接入，响应 connected=false）----
  cameras: () => get('/api/cameras'),
  camera: (id) => get(`/api/cameras/${encodeURIComponent(id)}`),
  cameraPing: (ids) => {
    const q = ids && ids.length ? '?' + ids.map((i) => `ids=${encodeURIComponent(i)}`).join('&') : ''
    return post(`/api/cameras/ping${q}`)
  },
  mapTrack: (person) => get(`/api/map/track?person=${encodeURIComponent(person)}`),
  monitorCameras: () => get('/api/monitor/cameras'),
  monitorEdges: () => get('/api/monitor/edges'),
  k8sWorkloads: () => get('/api/k8s/workloads'),
  k8sRollout: (plan) => postJson('/api/k8s/rollout', plan),
  watchlistAlerts: (limit = 50) => get(`/api/watchlist/alerts?limit=${limit}`),
}
