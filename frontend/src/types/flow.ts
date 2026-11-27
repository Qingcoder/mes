/** 流程选项：工艺管理里的流程分组，或历史工单用过的站点序列。 */
export interface FlowOption {
  /** 唯一标识：工艺流程为 config:<groupId>，历史流程为 history:<woId> */
  key: string
  /** 下拉/列表展示文案 */
  label: string
  /** 流程名称；历史流程没有独立名称，退化为站点序列 */
  name: string
  /** 该流程的站点序列（按过站顺序） */
  stations: string[]
  source: 'config' | 'history'
}

/** 工单上记录的流程组合明细 */
export interface WoFlowSelection {
  key: string
  name: string
  stations: string[]
}
