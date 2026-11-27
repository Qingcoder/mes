export interface FixedModule {
  key: string
  label: string
  route: string
  icon: string
  permission: string
  order: number
  description: string
}

export const FIXED_MODULES: FixedModule[] = [
  {
    key: 'dashboard',
    label: '看板',
    route: '/dashboard',
    icon: 'dashboard',
    permission: 'dashboard:view',
    order: 7,
    description: '展示工单、生产报工、设备状态、质量检验等关键指标的汇总视图。',
  },
  {
    key: 'person',
    label: '人员管理',
    route: '/person',
    icon: 'person',
    permission: 'person:manage',
    order: 8,
    description: '维护员工档案、部门/产线/班组归属、岗位角色与系统账号，控制工单管理、生产报工、物料追溯、设备状态、质量检验等模块的访问权限。',
  },
  {
    key: 'machine',
    label: '设备管理',
    route: '/machine',
    icon: 'machine',
    permission: 'machine:manage',
    order: 9,
    description: '管理设备台账、运行/停机/维修状态、点检维护记录及设备使用环境，支撑生产报工与设备状态联动。',
  },
  {
    key: 'material',
    label: '物料管理',
    route: '/material',
    icon: 'material',
    permission: 'material:manage',
    order: 10,
    description: '管理仓库成品台账与批次追溯，关联工单领料、包装出库和材料环境/配置，支撑成品追溯。',
  },
  {
    key: 'method',
    label: '工艺管理',
    route: '/method',
    icon: 'method',
    permission: 'method:manage',
    order: 11,
    description: '维护工艺流程、作业指导、站点顺序与不良代码规则，支撑过站报工、返修流转和工艺追溯。',
  },
  {
    key: 'environment',
    label: '共享资料库',
    route: '/environment',
    icon: 'environment',
    permission: 'environment:manage',
    order: 12,
    description: '统一上传、查看、下载和更新共享资料，关联人员、产品、设备与工艺，供各模块共同使用。',
  },
]

export function fixedModuleByKey(key: string): FixedModule | undefined {
  return FIXED_MODULES.find(m => m.key === key)
}
