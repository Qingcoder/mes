// 临时校验脚本：确认本轮改动已进入构建产物（用完即删）
import fs from 'node:fs'
import path from 'node:path'

const assetsDir = path.resolve('dist/assets')
const files = fs.readdirSync(assetsDir).filter(f => f.endsWith('.js'))
const content = files.map(f => fs.readFileSync(path.join(assetsDir, f), 'utf8')).join('\n')
const keys = ['人员详情与统筹范围', '变更角色', '人机料法环', 'relatedStations', 'personScope', '没有符合筛选条件的设备']
for (const k of keys) console.log(`${k} => ${content.includes(k)}`)
console.log(`js files: ${files.join(', ')}`)
