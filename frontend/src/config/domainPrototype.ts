export interface DomainPrototypeConfig {
  key: string
  title: string
  sections: string[]
  tabs: string[]
  actions: string[]
  detailFields: string[]
}

const COMMON_TABS = ['概览', '列表', '配置', '关联']
const COMMON_ACTIONS = ['新增', '导入', '刷新', '导出']
const COMMON_FIELDS = ['编号', '名称', '状态', '更新时间', '备注']

function build(
  key: string,
  title: string,
  sections: string[],
  detailFields: string[] = COMMON_FIELDS,
): DomainPrototypeConfig {
  return {
    key,
    title,
    sections,
    tabs: [...COMMON_TABS],
    actions: [...COMMON_ACTIONS],
    detailFields: [...detailFields],
  }
}

export const DOMAIN_PROTOTYPES: Record<string, DomainPrototypeConfig> = {
  dashboard: build('dashboard', '看板', [
    '生产总览', '工单进度', '设备状态', '质量指标',
  ], ['指标名称', '当前值', '目标值', '状态', '更新时间', '备注']),
  person: build('person', '人员管理', [
    '员工档案', '岗位角色', '账号授权', '操作审计',
  ], ['工号', '姓名', '部门', '岗位角色', '状态', '备注']),
  machine: build('machine', '设备管理', [
    '设备台账', '运行/停机/维修状态', '点检维护记录', '生产报工关联',
  ], ['设备编号', '设备名称', '运行状态', '使用工位', '点检人', '备注']),
  material: build('material', '物料管理', [
    '仓库成品台账', '批次追溯', '工单领料', '包装出库',
  ], ['物料编码', '物料名称', '批次', '数量', '关联工单', '备注']),
  method: build('method', '工艺管理', [
    '工艺流程', '作业指导', '站点顺序', '不良代码规则',
  ], ['流程编码', '流程名称', '站点顺序', '作业规则', '状态', '备注']),
  environment: build('environment', '环境配置', [
    '部门/产线', '工位/站点', '存储环境', '软硬件配置',
  ], ['配置编码', '配置名称', '类型', '适用对象', '状态', '备注']),
}

export function domainPrototypeFor(key: string): DomainPrototypeConfig {
  return DOMAIN_PROTOTYPES[key] || build(key, key || '领域模块', ['模块一', '模块二', '模块三'])
}
