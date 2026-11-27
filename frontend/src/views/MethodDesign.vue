<template>
  <div class="method-page">
    <div class="head">
      <div>
        <h2>工艺管理 · 站点设计</h2>
        <p class="sub">先落地站点设计：配置站点布局、工艺参数、作业指导、不良代码与回站关系；当前设计数据尚未替换过站执行配置。</p>
      </div>
      <div class="row">
        <button class="btn" type="button" @click="router.push('/')">返回首页</button>
        <button class="btn" type="button" @click="openDefectLibrary(false)">不良代码库</button>
        <button class="btn" type="button" :disabled="saving" @click="reload">重新加载</button>
        <button class="btn primary" type="button" :disabled="saving || !dirty" @click="save()">
          {{ saving ? '保存中…' : dirty ? '保存设计' : '已保存' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="msg err">{{ error }}</div>
    <div v-else-if="notice" class="msg ok">{{ notice }}</div>
    <div v-if="loading" class="msg">正在加载工艺站点设计…</div>

    <template v-else-if="config">
      <div class="design-layout">
        <aside class="panel tree-panel">
          <div class="panel-head">
            <b>站点分组</b>
            <button class="btn sm" type="button" @click="addGroup">新增分组</button>
          </div>
          <div v-for="group in sortedGroups" :key="group.id" class="group-block">
            <div class="group-row">
              <b>{{ group.name }}</b>
              <span class="count">{{ groupStations(group.id).length }}</span>
              <button class="link danger-link" type="button" @click="removeGroup(group)">删除</button>
            </div>
            <button
              v-for="station in groupStations(group.id)"
              :key="station.id"
              class="station-node"
              :class="{ active: station.id === selectedId, disabled: station.enabled === false }"
              type="button"
              @click="selectedId = station.id"
              @dblclick.stop="openStationEdit(station)"
            >
              <span class="node-code mono">{{ station.code }}</span>
              <span class="node-name">{{ station.name }}</span>
              <span class="node-type">{{ typeLabel(station.type) }}</span>
            </button>
          </div>
          <button class="btn full" type="button" @click="addStation">新增站点</button>
          <button class="btn full" type="button" @click="openLibrary('manage')">站点库</button>
        </aside>

        <main class="panel canvas-panel">
          <div class="panel-head">
            <b>站点卡片布局</b>
            <span class="mini">{{ dragStatus || '拖动卡片左上角手柄调整顺序' }}</span>
          </div>
          <div class="canvas">
            <section v-for="section in stationSections" :key="section.key" class="station-section" :class="`section-${section.key}`">
              <div class="section-title">
                <b>{{ section.title }}</b>
                <span class="mini">{{ section.hint }}</span>
              </div>
              <div class="station-card-grid" :class="{ 'is-dragging': drag.active && drag.section === section.key }">
                <article
                  v-for="(station, index) in section.stations"
                  :key="station.id"
                  :data-station-card="station.id"
                  class="station-card"
                  :class="{
                    active: station.id === selectedId,
                    dragging: drag.id === station.id,
                    disabled: station.enabled === false,
                    'drop-before': drag.targetId === station.id && drag.position === 'before',
                    'drop-after': drag.targetId === station.id && drag.position === 'after',
                  }"
                  @click="selectStation(station)"
                  @dblclick.stop="openStationEdit(station)"
                >
                  <div class="card-top">
                    <span class="drag-handle" title="拖动排序" aria-label="拖动排序" @pointerdown.stop.prevent="startDrag($event, station)">⠿</span>
                    <span class="order-badge">{{ index + 1 }}</span>
                    <span class="card-code mono">{{ station.code }}</span>
                    <span v-if="station.enabled === false" class="disabled-tag">停用</span>
                  </div>
                  <b class="card-name">{{ station.name }}</b>
                  <button class="link card-detail-link" type="button" @click.stop="openStationDetail(station)">查看详情页</button>
                  <div class="card-meta">
                    <span class="type-tag">{{ typeLabel(station.type) }}</span>
                    <span class="group-tag">{{ groupName(station.groupId) }}</span>
                  </div>
                  <div class="card-stats">
                    <span>{{ station.params?.length || 0 }} 参数</span>
                    <span>{{ station.failCodes?.length || 0 }} 不良码</span>
                    <span>{{ station.workInstruction ? '有作业指导' : '无作业指导' }}</span>
                  </div>
                </article>
              </div>
            </section>
            <div v-if="!sortedStations.length" class="empty-line">暂无站点，点击左侧“新增站点”创建。</div>
          </div>

          <div class="settings-strip temporarily-hidden">
            <label>分配策略
              <select v-model="config.settings.assignPolicy" @change="markDirty">
                <option value="first">首站分配</option>
                <option value="pendingFirst">待过站优先</option>
              </select>
            </label>
            <label>SN 池范围
              <select v-model="config.settings.snPoolScope" @change="markDirty">
                <option value="workOrder">按工单</option>
              </select>
            </label>
            <label>不良码范围
              <select v-model="config.settings.failCodeScope" @change="markDirty">
                <option value="station">按站点</option>
              </select>
            </label>
            <label>维修站点
              <select v-model="config.settings.repairStationId" @change="markDirty">
                <option value="">未设置</option>
                <option v-for="s in sortedStations" :key="s.id" :value="s.id">{{ s.code }} · {{ s.name }}</option>
              </select>
            </label>
          </div>

          <div class="relation-card temporarily-hidden">
            <b>与生产数据的关联</b>
            <div class="relation-grid">
              <div><label>工单站点序列</label><b class="mono">wos.stations[]</b><small>{{ stationCodes || '暂无站点' }}</small></div>
              <div><label>SN 当前站点</label><b class="mono">units.current_station</b><small>过站时按站点编码定位</small></div>
              <div><label>过站记录</label><b class="mono">station_records.station</b><small>记录每个站点的处理结果</small></div>
              <div><label>站点权限</label><b class="mono">access_control</b><small>按站点名称 / 编号授权</small></div>
            </div>
          </div>
        </main>

        <aside class="panel detail-panel">
          <template v-if="selected">
            <div class="panel-head">
              <b>站点属性</b>
              <span class="mini mono">{{ selected.code }}</span>
            </div>
            <div class="form-grid">
              <label>站点编码
                <span class="code-picker">
                  <input :value="selected.code" readonly />
                  <button class="btn sm" type="button" @click="openLibrary('select')">选择</button>
                </span>
              </label>
              <label>站点名称<input v-model="selected.name" title="保存设计后按站点编码同步到站点库" @input="markDirty" /></label>
              <label>站点类型
                <select v-model="selected.type" @change="markDirty">
                  <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
              </label>
              <label>所属分组
                <select v-model="selected.groupId" @change="markDirty">
                  <option v-for="g in sortedGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
                </select>
              </label>
              <label>顺序<input type="number" min="1" v-model.number="selected.order" @input="markDirty" /></label>
              <label class="check-line"><input type="checkbox" v-model="selected.enabled" @change="markDirty" /> 启用</label>
            </div>

            <div class="temporarily-hidden">
              <div class="field">
                <label>站点说明</label>
                <textarea v-model="selected.description" rows="2" @input="markDirty"></textarea>
              </div>
              <div class="field">
                <label>作业指导</label>
                <textarea v-model="selected.workInstruction" rows="3" placeholder="填写本站点作业要求、操作步骤或注意事项" @input="markDirty"></textarea>
              </div>
              <div class="field">
                <label>维修后回站目标</label>
                <select v-model="selected.returnStationId" @change="markDirty">
                  <option value="">不设置</option>
                  <option v-for="s in otherStations" :key="s.id" :value="s.id">{{ s.code }} · {{ s.name }}</option>
                </select>
              </div>

              <div class="detail-actions">
                <button class="btn sm" type="button" :disabled="!canMove(-1)" @click="move(-1)">上移</button>
                <button class="btn sm" type="button" :disabled="!canMove(1)" @click="move(1)">下移</button>
                <button class="btn sm danger" type="button" @click="removeStation">删除站点</button>
              </div>
            </div>

            <div class="section-head">
              <b>工艺参数</b>
            </div>
            <ResumableUploader
              :station-id="selected.id"
              accept="*/*"
              :max-size="200 * 1024 * 1024"
              :max-files="10"
              label="拖拽文件到此处，或点击选择"
              hint="任意文件均可作为参考附件；支持断点续传，最大 200MB。"
              @uploaded="onParamFileUploaded"
              @error="paramFileError = $event"
            />
            <div class="param-rule">
              上传内容均为参考附件，不参与工艺参数解析。
            </div>
            <div v-if="paramFileError" class="msg err">{{ paramFileError }}</div>
            <div v-if="paramFileNotice" class="msg ok">{{ paramFileNotice }}</div>
            <div v-if="selected.paramFiles?.length" class="param-file-list">
              <div v-for="file in selected.paramFiles" :key="file.id" class="param-file-row">
                <span>{{ file.name }}</span>
                <small class="mono">{{ formatFileSize(file.size) }} · {{ file.parseable ? '可解析' : '参考附件' }}</small>
                <button class="link" type="button" @click="downloadParamFile(file)">下载</button>
                <button class="link danger-link" type="button" @click="deleteParamFile(file)">移除</button>
              </div>
            </div>
            <div v-if="selected.params?.length" class="param-list">
              <div class="param-head param-config-row">
                <span>标识</span><span>名称</span><span>值</span><span>单位</span><span>必填</span><span></span>
              </div>
              <div v-for="(param, index) in selected.params" :key="index" class="param-row param-config-row">
                <input v-model="param.key" placeholder="标识" @input="markDirty" />
                <input v-model="param.label" placeholder="名称" @input="markDirty" />
                <input v-model="param.value" placeholder="值" @input="markDirty" />
                <input v-model="param.unit" placeholder="单位" @input="markDirty" />
                <label class="param-required"><input type="checkbox" v-model="param.required" @change="markDirty" /> 必填</label>
                <button class="link danger-link" type="button" @click="selected.params.splice(index, 1); markDirty()">删除</button>
              </div>
            </div>
            <div v-else class="empty-box">暂无工艺参数，可手动新增或导入 Excel/CSV</div>

            <div class="temporarily-hidden">
              <div class="section-head">
                <b>不良代码</b>
                <button class="btn sm" type="button" @click="addFailCode">新增代码</button>
              </div>
              <div v-if="selected.failCodes?.length" class="param-list">
                <div v-for="(item, index) in selected.failCodes" :key="index" class="param-row">
                  <input v-model="item.code" placeholder="代码" @input="markDirty" />
                  <input v-model="item.name" placeholder="名称" @input="markDirty" />
                  <button class="link danger-link" type="button" @click="selected.failCodes.splice(index, 1); markDirty()">删除</button>
                </div>
              </div>
              <div v-else class="empty-box">暂无不良代码</div>

              <div class="detail-actions">
                <button class="btn sm" type="button" :disabled="!canMove(-1)" @click="move(-1)">上移</button>
                <button class="btn sm" type="button" :disabled="!canMove(1)" @click="move(1)">下移</button>
                <button class="btn sm danger" type="button" @click="removeStation">删除站点</button>
              </div>
            </div>
          </template>
          <div v-else class="empty-box tall">请选择左侧站点</div>
        </aside>
      </div>
    </template>

    <div v-if="libraryOpen" class="modal-mask" @click.self="closeLibrary">
      <div class="modal library-modal" role="dialog" aria-modal="true">
        <div class="panel-head">
          <b>{{ libraryMode === 'manage' ? '维护站点库（名称/类型/说明按编码联动）' : '选择站点编码' }}</b>
          <div class="row">
            <button v-if="libraryMode === 'select'" class="btn sm" type="button" @click="switchLibraryMode('manage')">维护站点库</button>
            <button v-else class="btn sm" type="button" @click="switchLibraryMode('select')">返回选择</button>
            <button class="btn sm" type="button" @click="libraryOpen = false; router.push('/environment')">环境配置维护</button>
            <button class="btn sm" type="button" @click="closeLibrary">关闭</button>
          </div>
        </div>
        <p class="sub">
          {{ libraryMode === 'manage'
            ? '维护站点编码库。命名规则：类型前缀 + 序号；主线 OP10 起，检验 QC10 起，维修 R100 起，包装 PK10 起。'
            : '从站点库选择编码，应用到当前站点；库项维护请切换到“维护站点库”。' }}
        </p>
        <div v-if="libraryError" class="msg err">{{ libraryError }}</div>
        <div v-if="libraryNotice" class="msg ok">{{ libraryNotice }}</div>

        <div class="library-layout">
          <div class="library-tree">
            <div v-if="libraryMode === 'manage'" class="tree-toolbar">
              <b>站点库</b>
              <button class="link" type="button" @click="startAddingLibraryGroup">新增分组</button>
            </div>
            <div v-if="libraryMode === 'manage' && addingLibraryGroup" class="tree-edit-box">
              <input v-model="newLibraryGroup.name" placeholder="分组名称" />
              <input v-model="newLibraryGroup.prefix" class="mono" placeholder="前缀" maxlength="8" />
              <div>
                <button class="btn sm" type="button" @click="addLibraryGroup">添加</button>
                <button class="btn sm" type="button" @click="cancelAddingLibraryGroup">取消</button>
              </div>
            </div>
            <div v-for="group in sortedLibraryGroups" :key="group.id" class="library-group">
              <div class="library-group-head">
                <button class="tree-main" type="button" @click="toggleLibraryGroup(group.id); libraryItemGroupId = group.id; libraryItemId = ''">
                  <span>{{ expandedLibrary[group.id] ? '▾' : '▸' }}</span>
                  <b>{{ group.name }}</b>
                  <small class="mono">{{ group.prefix }}</small>
                  <span class="count">{{ (group.items || []).length }}</span>
                </button>
                <template v-if="libraryMode === 'manage'">
                  <button class="link" type="button" @click="startEditLibraryGroup(group)">编辑</button>
                  <button class="link" type="button" @click="startAddingLibraryItem(group)">新增</button>
                  <button class="link danger-link" type="button" :disabled="libraryGroupUsedCount(group) > 0" @click="removeLibraryGroup(group)">删除</button>
                </template>
              </div>
              <div v-if="libraryMode === 'manage' && editingLibraryGroupId === group.id" class="tree-edit-box">
                <input v-model="libraryGroupDraft.name" placeholder="分组名称" />
                <input v-model="libraryGroupDraft.prefix" class="mono" placeholder="前缀" maxlength="8" />
                <input v-model.number="libraryGroupDraft.start" type="number" min="1" title="起始序号" />
                <input v-model.number="libraryGroupDraft.step" type="number" min="1" title="递增长度" />
                <div>
                  <button class="btn sm primary" type="button" @click="saveLibraryGroupEdit(group)">保存</button>
                  <button class="btn sm" type="button" @click="cancelLibraryTreeEdit">取消</button>
                </div>
              </div>
              <div v-if="libraryMode === 'manage' && addingLibraryItemGroupId === group.id" class="tree-edit-box">
                <input v-model="newTreeItem.name" placeholder="库项名称" />
                <select v-model="newTreeItem.type">
                  <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
                <div>
                  <button class="btn sm primary" type="button" @click="addTreeLibraryItem(group)">添加</button>
                  <button class="btn sm" type="button" @click="cancelLibraryTreeEdit">取消</button>
                </div>
              </div>
              <div v-if="expandedLibrary[group.id]" class="library-items">
                <div
                  v-for="item in group.items || []"
                  :key="item.id"
                  class="library-item"
                  :class="{ active: libraryItemId === item.id, used: libraryUsedCodes.includes(item.code) }"
                >
                  <button class="tree-main" type="button" @click="libraryItemId = item.id; libraryItemGroupId = group.id">
                    <span class="mono">{{ item.code }}</span>
                    <span>{{ item.name }}</span>
                    <small>{{ libraryUsedCodes.includes(item.code) ? '已使用' : '可用' }}</small>
                  </button>
                  <template v-if="libraryMode === 'manage'">
                    <button class="link" type="button" @click="startEditLibraryItem(item)">编辑</button>
                    <button class="link danger-link" type="button" :disabled="libraryUsedCodes.includes(item.code)" @click="removeLibraryItem(item)">删除</button>
                  </template>
                </div>
                <div v-if="libraryMode === 'manage' && editingLibraryItemId && (group.items || []).some((i: any) => i.id === editingLibraryItemId)" class="tree-edit-box">
                  <input v-model="libraryItemDraft.name" placeholder="库项名称" />
                  <select v-model="libraryItemDraft.type">
                    <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
                  </select>
                  <div>
                    <button class="btn sm primary" type="button" @click="saveLibraryItemEdit">保存</button>
                    <button class="btn sm" type="button" @click="cancelLibraryTreeEdit">取消</button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div v-if="libraryMode === 'select'" class="library-form">
            <template v-if="activeLibraryItem">
              <h4>库项详情</h4>
              <div class="library-detail">
                <div><label>编码</label><b class="mono">{{ activeLibraryItem.code }}</b></div>
                <div><label>名称</label><b>{{ activeLibraryItem.name }}</b></div>
                <div><label>类型</label><b>{{ typeLabel(activeLibraryItem.type) }}</b></div>
              </div>
              <div class="library-actions">
                <button class="btn primary" type="button" :disabled="!selected" @click="applyLibraryItem">应用到当前站点</button>
              </div>
              <p class="mini">当前站点：{{ selected ? `${selected.code} · ${selected.name}` : '未选择' }}</p>
            </template>
            <div v-else class="empty-box tall">请从左侧站点库选择一个编码</div>
          </div>

          <div v-else class="library-form">
            <template v-if="activeLibraryItem">
              <h4>库项详情</h4>
              <div class="library-detail">
                <div><label>编码</label><b class="mono">{{ activeLibraryItem.code }}</b></div>
                <div><label>名称</label><input v-model="activeLibraryItem.name" @input="markLibraryDirty" /></div>
                <div><label>类型</label>
                  <select v-model="activeLibraryItem.type" @change="markLibraryDirty">
                    <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
                  </select>
                </div>
              </div>
              <div class="library-actions">
                <button class="btn" type="button" :disabled="libraryUsedCodes.includes(activeLibraryItem.code)" @click="removeLibraryItem">删除库项</button>
              </div>
            </template>

            <h4>站点类型</h4>
            <div class="type-list">
              <div v-for="(type, index) in typeOptions" :key="type.value" class="type-row">
                <span class="mono">{{ type.value }}</span>
                <input v-model="typeOptions[index].label" @input="markLibraryDirty" />
                <button class="link danger-link" type="button" :disabled="isTypeUsed(type.value)" @click="removeStationType(type)">删除</button>
              </div>
              <div class="type-add">
                <input v-model="newTypeLabel" placeholder="新增类型名称" />
                <button class="btn sm" type="button" @click="addStationType">新增类型</button>
              </div>
            </div>

            <h4>新增库项</h4>
            <div class="library-form-grid">
              <label>所属分组
                <select v-model="libraryItemGroupId">
                  <option v-for="group in sortedLibraryGroups" :key="group.id" :value="group.id">{{ group.name }}（{{ group.prefix }}）</option>
                </select>
              </label>
              <label>名称<input v-model="libraryItemName" placeholder="如：终检站" /></label>
              <label>类型
                <select v-model="libraryItemType">
                  <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
                </select>
              </label>
              <div class="code-preview">自动生成编码：<b class="mono">{{ nextLibraryCodePreview }}</b></div>
              <div class="library-actions">
                <button class="btn" type="button" @click="addLibraryItem">新增库项</button>
                <button class="btn danger" type="button" :disabled="!activeLibraryItem || libraryUsedCodes.includes(activeLibraryItem.code)" @click="removeLibraryItem">删除库项</button>
              </div>
            </div>

            <h4>新增库分组</h4>
            <div class="library-form-grid">
              <label>分组名称<input v-model="newLibraryGroup.name" /></label>
              <label>编码前缀<input v-model="newLibraryGroup.prefix" maxlength="4" /></label>
              <label>起始序号<input type="number" min="1" v-model.number="newLibraryGroup.start" /></label>
              <label>递增长度<input type="number" min="1" v-model.number="newLibraryGroup.step" /></label>
              <div class="library-actions">
                <button class="btn" type="button" @click="addLibraryGroup">新增库分组</button>
                <button class="btn danger" type="button" :disabled="!activeLibraryGroup" @click="removeLibraryGroup">删除库分组</button>
              </div>
            </div>
          </div>
        </div>
        <div v-if="libraryMode === 'manage'" class="modal-foot">
          <button class="btn" type="button" @click="closeLibrary">取消</button>
          <button class="btn primary" type="button" @click="saveLibrary">保存站点库</button>
        </div>
      </div>
    </div>

    <div v-if="defectOpen" class="modal-mask defect-mask" @click.self="closeDefectLibrary">
      <div class="modal defect-modal" role="dialog" aria-modal="true">
        <div class="panel-head">
          <b>{{ defectForStation ? '选择不良代码' : '不良代码库' }}</b>
          <div class="row">
            <button class="btn sm" type="button" @click="downloadDefectTemplate">下载模板</button>
            <button class="btn sm" type="button" @click="closeDefectLibrary">关闭</button>
          </div>
        </div>
        <p class="sub">按产品、工站、维修手段分类；编码自动生成，同类同名复用同一编码。</p>
        <div v-if="defectError" class="msg err">{{ defectError }}</div>
        <div v-if="defectNotice" class="msg ok">{{ defectNotice }}</div>

        <div class="defect-layout">
          <div class="defect-list">
            <div class="toolbar inline">
              <input v-model="defectFilter.keyword" placeholder="搜索代码 / 名称" @keyup.enter="loadDefectCodes" />
              <select v-model="defectFilter.productCode" @change="loadDefectCodes"><option value="">全部产品</option><option v-for="p in defectOptions.products" :key="p.code" :value="p.code">{{ p.name }}</option></select>
              <select v-model="defectFilter.stationCode" @change="loadDefectCodes"><option value="">全部工站</option><option v-for="s in defectOptions.stations" :key="s.code" :value="s.code">{{ s.code }} · {{ s.name }}</option></select>
              <select v-model="defectFilter.repairMethod" @change="loadDefectCodes"><option value="">全部维修手段</option><option v-for="m in defectOptions.repairMethods" :key="m.code" :value="m.name">{{ m.name }}</option></select>
              <button class="btn sm" type="button" @click="loadDefectCodes">查询</button>
            </div>
            <div class="defect-table-wrap">
              <table>
                <thead><tr><th>编码</th><th>名称</th><th>分类</th><th>操作</th></tr></thead>
                <tbody>
                  <tr v-for="row in defectRows" :key="row.code">
                    <td class="mono">{{ row.code }}</td>
                    <td>{{ row.name }}</td>
                    <td class="mini">{{ row.productName || row.productCode || '全产品' }} / {{ row.stationName || row.stationCode || '全工站' }} / {{ row.repairMethod || '未分类' }}</td>
                    <td class="ops">
                      <button v-if="defectForStation" class="link" type="button" @click="selectDefectCode(row)">添加</button>
                      <button class="link" type="button" @click="editDefectCode(row)">编辑</button>
                      <button class="link danger-link" type="button" @click="removeDefectCode(row)">删除</button>
                    </td>
                  </tr>
                  <tr v-if="!defectRows.length"><td colspan="4" class="empty">暂无不良代码，可在右侧新增或导入模板</td></tr>
                </tbody>
              </table>
            </div>
          </div>
          <div class="defect-form-panel">
            <b>{{ editingDefectCode ? '编辑不良代码' : '新增不良代码' }}</b>
            <label>产品名称<select v-model="defectForm.productCode" @change="syncDefectProductName"><option value="">不限产品</option><option v-for="p in defectOptions.products" :key="p.code" :value="p.code">{{ p.name }}</option></select></label>
            <label>工站<select v-model="defectForm.stationCode" @change="syncDefectStationName"><option value="">不限工站</option><option v-for="s in defectOptions.stations" :key="s.code" :value="s.code">{{ s.code }} · {{ s.name }}</option></select></label>
            <label>维修手段<select v-model="defectForm.repairMethod"><option value="">未分类</option><option v-for="m in defectOptions.repairMethods" :key="m.code" :value="m.name">{{ m.name }}</option></select></label>
            <label>不良名称<input v-model="defectForm.name" placeholder="如：夹爪松动" /></label>
            <label>说明<textarea v-model="defectForm.description" rows="2" placeholder="可选"></textarea></label>
            <p class="mini">编码：{{ editingDefectCode || '保存后自动生成' }}</p>
            <div class="row">
              <button class="btn primary sm" type="button" :disabled="!defectForm.name.trim()" @click="saveDefectCode">{{ editingDefectCode ? '保存修改' : '新增代码' }}</button>
              <button v-if="editingDefectCode" class="btn sm" type="button" @click="resetDefectForm">取消编辑</button>
            </div>
            <div class="defect-import">
              <b>按模板导入</b>
              <input type="file" accept=".xlsx,.xls,.csv" @change="importDefectFile" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="stationEditOpen" class="modal-mask" @click.self="closeStationEdit">
      <div class="modal station-edit-modal" role="dialog" aria-modal="true">
        <div class="panel-head">
          <b>编辑站点</b>
          <button class="btn sm" type="button" @click="closeStationEdit">关闭</button>
        </div>
        <div v-if="stationEditError" class="msg err">{{ stationEditError }}</div>
        <form class="station-edit-form" @submit.prevent="saveStationEdit">
          <label>站点编码<input :value="stationEditForm.code" readonly /></label>
          <label class="full">站点名称<input v-model="stationEditForm.name" autofocus /></label>
          <label>站点类型
            <select v-model="stationEditForm.type">
              <option v-for="t in typeOptions" :key="t.value" :value="t.value">{{ t.label }}</option>
            </select>
          </label>
          <label>所属分组
            <select v-model="stationEditForm.groupId">
              <option v-for="g in sortedGroups" :key="g.id" :value="g.id">{{ g.name }}</option>
            </select>
          </label>
          <label>顺序<input type="number" min="1" v-model.number="stationEditForm.order" /></label>
          <label class="check-line"><input type="checkbox" v-model="stationEditForm.enabled" /> 启用</label>

          <div class="relation-block full">
            <div class="section-head"><b>关联对象</b><span class="mini">与设备 / 人员 / 工单自动同步</span></div>
            <div class="relation-edit-grid">
              <div>
                <span>关联产品</span>
                <div class="option-list">
                  <label v-for="item in stationOptions.products" :key="'p-' + item.code">
                    <input type="checkbox" :checked="hasRelation('relatedProducts', item.code)" @change="toggleRelation('relatedProducts', item)" /> {{ item.code }} · {{ item.name }}
                  </label>
                  <div v-if="!stationOptions.products?.length" class="empty-mini">暂无产品</div>
                </div>
              </div>
              <div>
                <span>关联设备</span>
                <div class="option-list">
                  <label v-for="item in stationOptions.equipment" :key="'e-' + item.code">
                    <input type="checkbox" :checked="hasRelation('relatedEquipment', item.code)" @change="toggleRelation('relatedEquipment', item)" /> {{ item.code }} · {{ item.name }}
                  </label>
                  <div v-if="!stationOptions.equipment?.length" class="empty-mini">暂无设备</div>
                </div>
              </div>
              <div>
                <span>关联人员</span>
                <div class="option-list">
                  <label v-for="item in stationOptions.persons" :key="'u-' + item.code">
                    <input type="checkbox" :checked="hasRelation('relatedPersons', item.code)" @change="toggleRelation('relatedPersons', item)" /> {{ item.name }}（{{ item.code }}）
                  </label>
                  <div v-if="!stationOptions.persons?.length" class="empty-mini">暂无人员</div>
                </div>
              </div>
            </div>
          </div>

          <div class="fail-code-block full">
            <div class="section-head">
              <b>不良代码</b>
              <div class="row">
                <button class="btn sm" type="button" @click="openDefectLibrary(true)">从代码库添加</button>
                <button class="btn sm" type="button" @click="downloadDefectTemplate">下载模板</button>
              </div>
            </div>
            <p class="mini">编码由不良代码库自动生成；同类同名会复用已有编码，站点不再手填代码。</p>
            <div v-if="stationEditForm.failCodes?.length" class="edit-fail-list">
              <div v-for="(item, index) in stationEditForm.failCodes" :key="item.code || index" class="edit-fail-row">
                <input :value="item.code" class="mono" readonly />
                <input :value="item.name" readonly />
                <span class="mini">{{ item.productName || '全产品' }} / {{ item.stationName || item.stationCode || '全工站' }} / {{ item.repairMethod || '未分类' }}</span>
                <button class="link danger-link" type="button" @click="stationEditForm.failCodes.splice(index, 1)">移除</button>
              </div>
            </div>
            <div v-else class="empty-box">暂无不良代码，请从代码库添加</div>
          </div>

          <div class="modal-foot full">
            <button class="btn" type="button" @click="closeStationEdit">取消</button>
            <button class="btn primary" type="submit" :disabled="saving">{{ saving ? '保存中…' : '保存站点' }}</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { parseDefectCodeFile } from '../utils/import'
import ResumableUploader from '../components/ResumableUploader.vue'

const router = useRouter()
const route = useRoute()
const config = ref<any>(null)
const selectedId = ref('')
const loading = ref(true)
const saving = ref(false)
const dirty = ref(false)
const error = ref('')
const notice = ref('')
const paramFileError = ref('')
const paramFileNotice = ref('')
const drag = reactive({ active: false, id: '', targetId: '', position: '', section: '', wasDirty: false, changed: false })
let dragPointerId: number | null = null
let dragHandle: HTMLElement | null = null
const libraryOpen = ref(false)
const stationEditOpen = ref(false)
const stationEditError = ref('')
const stationEditForm = reactive<any>({ id: '', code: '', name: '', type: '', groupId: '', order: 1, enabled: true, failCodes: [], relatedProducts: [], relatedEquipment: [], relatedPersons: [] })
const stationOptions = reactive<any>({ products: [], equipment: [], persons: [] })
const defectOpen = ref(false)
const defectForStation = ref(false)
const defectRows = ref<any[]>([])
const defectError = ref('')
const defectNotice = ref('')
const editingDefectCode = ref('')
const defectOptions = reactive<any>({ products: [], stations: [], repairMethods: [] })
const defectFilter = reactive({ keyword: '', productCode: '', stationCode: '', repairMethod: '' })
const emptyDefectForm = () => ({ code: '', name: '', productCode: '', productName: '', stationCode: '', stationName: '', repairMethod: '', description: '' })
const defectForm = reactive<any>(emptyDefectForm())
const libraryMode = ref<'select' | 'manage'>('select')
const libraryItemId = ref('')
const libraryItemGroupId = ref('')
const libraryItemName = ref('')
const libraryItemType = ref('quality')
const newTypeLabel = ref('')
const libraryError = ref('')
const libraryNotice = ref('')
const expandedLibrary = reactive<Record<string, boolean>>({})
const newLibraryGroup = reactive({ name: '', prefix: '', start: 1, step: 10 })
const editingLibraryGroupId = ref('')
const editingLibraryItemId = ref('')
const addingLibraryGroup = ref(false)
const addingLibraryItemGroupId = ref('')
const libraryGroupDraft = reactive({ name: '', prefix: '', start: 1, step: 10 })
const libraryItemDraft = reactive({ name: '', type: 'quality' })
const newTreeItem = reactive({ name: '', type: 'quality' })
let librarySnapshot = ''
let libraryDirtyBefore = false
let libraryChanged = false

const sortedGroups = computed(() => [...(config.value?.groups || [])].sort((a, b) => (a.order || 0) - (b.order || 0)))
const sortedStations = computed(() => [...(config.value?.stations || [])].sort((a, b) => (a.order || 0) - (b.order || 0)))
const selected = computed(() => (config.value?.stations || []).find((s: any) => s.id === selectedId.value) || null)
const typeOptions = computed(() => config.value?.options?.stationTypes || [])
const otherStations = computed(() => sortedStations.value.filter((s: any) => s.id !== selectedId.value))
const stationCodes = computed(() => sortedStations.value.map((s: any) => s.code).join(' → '))
const sortedLibraryGroups = computed(() => [...(config.value?.library || [])].sort((a: any, b: any) => (a.order || 0) - (b.order || 0)))
const libraryUsedCodes = computed(() => sortedStations.value.map((s: any) => String(s.code || '').toUpperCase()))
const activeLibraryItem = computed(() => {
  for (const group of sortedLibraryGroups.value) {
    const item = (group.items || []).find((i: any) => i.id === libraryItemId.value)
    if (item) return item
  }
  return null
})
const activeLibraryGroup = computed(() => sortedLibraryGroups.value.find((g: any) => g.id === libraryItemGroupId.value) || null)
const nextLibraryCodePreview = computed(() => {
  const group = sortedLibraryGroups.value.find((g: any) => g.id === libraryItemGroupId.value)
  return group ? buildLibraryCode(group) : '—'
})
const independentTypeValues = computed(() => {
  const values = new Set<string>(['repair'])
  typeOptions.value.forEach((t: any) => {
    const text = `${t.label || ''} ${t.value || ''}`
    if (/维修|返修|repair/i.test(text)) values.add(String(t.value))
  })
  return values
})
function isRepairLikeType(value: string) { return independentTypeValues.value.has(String(value || '')) }
function stationSectionKey(station: any) { return isRepairLikeType(station?.type) ? 'repair' : 'main' }
function stationSectionLabel(station: any) { return stationSectionKey(station) === 'repair' ? '维修站点' : '主线站点' }
function stationsBySection(key: string) { return sortedStations.value.filter((s: any) => stationSectionKey(s) === key) }
const mainStations = computed(() => stationsBySection('main'))
const repairStations = computed(() => stationsBySection('repair'))
const stationSections = computed(() => [
  { key: 'main', title: '主线站点', hint: '按上下游顺序排列', stations: mainStations.value },
  ...(repairStations.value.length ? [{ key: 'repair', title: '维修 / 独立站点', hint: '独立处理，不参与主线顺序', stations: repairStations.value }] : []),
])
const dragStatus = computed(() => {
  if (!drag.active) return ''
  const source = sortedStations.value.find((s: any) => s.id === drag.id)
  const target = sortedStations.value.find((s: any) => s.id === drag.targetId)
  const section = drag.section === 'repair' ? '维修站点' : '主线站点'
  if (!source) return `正在调整${section}顺序`
  if (!target) return `${section}：正在移动 ${source.code}，拖到同区域卡片上`
  return `${section}：正在移动 ${source.code} → ${target.code}${drag.position === 'after' ? '之后' : '之前'}`
})

function typeLabel(value: string) {
  return typeOptions.value.find((t: any) => t.value === value)?.label || value || '未设置'
}
function groupName(groupId: string) {
  return sortedGroups.value.find((g: any) => g.id === groupId)?.name || '未分组'
}
function groupStations(groupId: string) {
  return sortedStations.value.filter((s: any) => s.groupId === groupId)
}
function repairGroupId() {
  const group = sortedGroups.value.find((g: any) => /维修|返修|repair/i.test(`${g.name || ''} ${g.id || ''}`))
  return group?.id || ''
}
function selectStation(station: any) {
  if (!drag.active) selectedId.value = station.id
}
function openStationDetail(station: any) {
  selectedId.value = station.id
  router.push({ path: `/method/station/${encodeURIComponent(station.code || '')}` })
}
function hasRelation(field: string, code: string) {
  return (stationEditForm[field] || []).some((item: any) => item.code === code)
}
function toggleRelation(field: string, item: any) {
  const code = String(item.code || '')
  if (!code) return
  const list = stationEditForm[field] || []
  const index = list.findIndex((row: any) => row.code === code)
  if (index >= 0) list.splice(index, 1)
  else list.push({ code, name: String(item.name || code) })
}
async function loadStationOptions() {
  try {
    const data = await api.processDesignOptions()
    Object.assign(stationOptions, {
      products: data.products || [],
      equipment: data.equipment || [],
      persons: data.persons || [],
    })
  } catch {
    Object.assign(stationOptions, { products: [], equipment: [], persons: [] })
  }
}
function openStationEdit(station: any) {
  selectedId.value = station.id
  stationEditError.value = ''
  void loadStationOptions()
  Object.assign(stationEditForm, {
    id: station.id,
    code: station.code,
    name: station.name || '',
    type: station.type || 'normal',
    groupId: station.groupId || '',
    order: Number(station.order) || 1,
    enabled: station.enabled !== false,
    failCodes: (station.failCodes || []).map((item: any) => ({ code: String(item.code || ''), name: String(item.name || '') })),
    relatedProducts: (station.relatedProducts || []).map((item: any) => ({ code: String(item.code || ''), name: String(item.name || '') })),
    relatedEquipment: (station.relatedEquipment || []).map((item: any) => ({ code: String(item.code || ''), name: String(item.name || '') })),
    relatedPersons: (station.relatedPersons || []).map((item: any) => ({ code: String(item.code || ''), name: String(item.name || '') })),
  })
  stationEditOpen.value = true
}
function addEditFailCode() {
  void openDefectLibrary(true)
}
async function loadDefectOptions() {
  try {
    const data: any = await api.defectCodeOptions()
    Object.assign(defectOptions, {
      products: data.products || [],
      stations: data.stations || [],
      repairMethods: data.repairMethods || [],
    })
  } catch { /* 选项加载失败不阻塞代码库 */ }
}
async function loadDefectCodes() {
  try { defectRows.value = await api.defectCodes(defectFilter) }
  catch (e: any) { defectError.value = e.message || '不良代码库加载失败' }
}
async function openDefectLibrary(forStation: boolean) {
  defectForStation.value = forStation
  defectError.value = ''
  defectNotice.value = ''
  resetDefectForm()
  await loadDefectOptions()
  if (forStation && stationEditForm.code) defectFilter.stationCode = stationEditForm.code
  await loadDefectCodes()
  defectOpen.value = true
}
function closeDefectLibrary() {
  defectOpen.value = false
  defectError.value = ''
  defectNotice.value = ''
}
function syncDefectProductName() {
  defectForm.productName = (defectOptions.products || []).find((p: any) => p.code === defectForm.productCode)?.name || ''
}
function syncDefectStationName() {
  defectForm.stationName = (defectOptions.stations || []).find((s: any) => s.code === defectForm.stationCode)?.name || ''
}
function resetDefectForm() {
  editingDefectCode.value = ''
  Object.assign(defectForm, emptyDefectForm())
}
function editDefectCode(row: any) {
  editingDefectCode.value = row.code
  Object.assign(defectForm, {
    code: row.code, name: row.name || '', productCode: row.productCode || '', productName: row.productName || '',
    stationCode: row.stationCode || '', stationName: row.stationName || '', repairMethod: row.repairMethod || '', description: row.description || '',
  })
}
async function saveDefectCode() {
  defectError.value = ''
  defectNotice.value = ''
  try {
    const payload = { ...defectForm }
    if (editingDefectCode.value) {
      const saved: any = await api.updateDefectCode(editingDefectCode.value, payload)
      defectNotice.value = `已保存 ${saved.code}`
    } else {
      const saved: any = await api.createDefectCode(payload)
      defectNotice.value = `已生成编码 ${saved.code}`
    }
    resetDefectForm()
    await loadDefectCodes()
  } catch (e: any) { defectError.value = e.message || '不良代码保存失败' }
}
async function removeDefectCode(row: any) {
  if (!window.confirm(`确认删除不良代码 ${row.code}？`)) return
  try {
    await api.deleteDefectCode(row.code)
    await loadDefectCodes()
    if (editingDefectCode.value === row.code) resetDefectForm()
  } catch (e: any) { defectError.value = e.message || '删除失败' }
}
function selectDefectCode(row: any) {
  if (!stationEditForm.failCodes.some((item: any) => item.code === row.code)) {
    stationEditForm.failCodes.push({
      code: row.code, name: row.name, productCode: row.productCode, productName: row.productName,
      stationCode: row.stationCode, stationName: row.stationName, repairMethod: row.repairMethod,
    })
  }
  defectOpen.value = false
}
async function downloadDefectTemplate() {
  try {
    const blob = await api.defectCodeTemplate()
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = '不良代码导入模板.csv'
    link.click()
    URL.revokeObjectURL(url)
  } catch (e: any) { defectError.value = e.message || '模板下载失败' }
}
async function importDefectFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  defectError.value = ''
  const parsed = await parseDefectCodeFile(file)
  if (parsed.errorMessage) { defectError.value = parsed.errorMessage; input.value = ''; return }
  try {
    const result: any = await api.importDefectCodes(parsed.rows)
    defectNotice.value = `导入完成：新增 ${result.created}，复用 ${result.reused}，失败 ${result.failed.length}`
    await loadDefectCodes()
  } catch (e: any) { defectError.value = e.message || '导入失败' }
  input.value = ''
}
function closeStationEdit() {
  stationEditOpen.value = false
  stationEditError.value = ''
}
async function saveStationEdit() {
  stationEditError.value = ''
  const name = String(stationEditForm.name || '').trim()
  if (!name) { stationEditError.value = '请输入站点名称'; return }
  const target = (config.value?.stations || []).find((s: any) => s.id === stationEditForm.id)
  if (!target) { stationEditError.value = '站点不存在'; return }
  target.name = name
  target.type = String(stationEditForm.type || 'normal')
  target.groupId = String(stationEditForm.groupId || '')
  target.order = Number(stationEditForm.order) || 1
  target.enabled = !!stationEditForm.enabled
  target.failCodes = (stationEditForm.failCodes || [])
    .map((item: any) => ({
      code: String(item.code || '').trim(),
      name: String(item.name || '').trim(),
      productCode: String(item.productCode || '').trim(),
      productName: String(item.productName || '').trim(),
      stationCode: String(item.stationCode || '').trim(),
      stationName: String(item.stationName || '').trim(),
      repairMethod: String(item.repairMethod || '').trim(),
    }))
    .filter((item: any) => item.code)
  const cleanRelations = (rows: any[]) => {
    const seen = new Set<string>()
    return (rows || [])
      .map((item: any) => ({ code: String(item.code || '').trim(), name: String(item.name || '').trim() }))
      .filter((item: any) => item.code && !seen.has(item.code) && seen.add(item.code))
  }
  target.relatedProducts = cleanRelations(stationEditForm.relatedProducts)
  target.relatedEquipment = cleanRelations(stationEditForm.relatedEquipment)
  target.relatedPersons = cleanRelations(stationEditForm.relatedPersons)
  const ok = await save('站点编辑已保存')
  if (ok) closeStationEdit()
}
function markDirty() {
  dirty.value = true
  notice.value = ''
}
function newId(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 1000)}`
}
function addGroup() {
  const order = sortedGroups.value.length + 1
  config.value.groups.push({ id: newId('grp'), name: `新分组 ${order}`, description: '', order })
  markDirty()
}
function removeGroup(group: any) {
  if (groupStations(group.id).length) {
    error.value = '请先移走或删除该分组下的站点'
    return
  }
  config.value.groups = config.value.groups.filter((g: any) => g.id !== group.id)
  markDirty()
}
function allLibraryItems() {
  return sortedLibraryGroups.value.flatMap((group: any) => group.items || [])
}
function buildLibraryCode(group: any) {
  const prefix = String(group.prefix || '').toUpperCase().replace(/[^A-Z0-9]/g, '') || 'OP'
  const step = Math.max(1, Number(group.step) || 10)
  const used = new Set(allLibraryItems().map((item: any) => String(item.code || '').toUpperCase()))
  const nums = (group.items || [])
    .map((item: any) => new RegExp(`^${prefix}(\\d+)$`).exec(String(item.code || '').toUpperCase()))
    .filter(Boolean)
    .map((match: RegExpExecArray | null) => Number(match![1]))
  let next = nums.length ? Math.max(...nums) + step : (Number(group.start) || step)
  while (used.has(`${prefix}${next}`)) next += step
  return `${prefix}${next}`
}
function defaultLibraryItem() {
  const used = new Set(libraryUsedCodes.value)
  return allLibraryItems().find((item: any) => !used.has(String(item.code || '').toUpperCase())) || null
}
function findLibraryItemByCode(code: string) {
  const upper = String(code || '').toUpperCase()
  return allLibraryItems().find((item: any) => String(item.code || '').toUpperCase() === upper) || null
}
function openLibrary(mode: 'select' | 'manage' = 'select') {
  if (!config.value) return
  cancelLibraryTreeEdit()
  libraryMode.value = mode
  librarySnapshot = JSON.stringify(config.value.library || [])
  libraryDirtyBefore = dirty.value
  libraryChanged = false
  libraryError.value = ''
  libraryNotice.value = ''
  const current = findLibraryItemByCode(selected.value?.code || '') || defaultLibraryItem()
  libraryItemId.value = current?.id || ''
  libraryItemGroupId.value = sortedLibraryGroups.value.find((g: any) => (g.items || []).some((i: any) => i.id === current?.id))?.id || sortedLibraryGroups.value[0]?.id || ''
  libraryItemName.value = ''
  libraryItemType.value = typeOptions.value[0]?.value || ''
  sortedLibraryGroups.value.forEach((group: any) => { expandedLibrary[group.id] = true })
  libraryOpen.value = true
}
function closeLibrary() {
  cancelLibraryTreeEdit()
  if (libraryChanged) {
    config.value.library = JSON.parse(librarySnapshot)
    dirty.value = libraryDirtyBefore
    libraryChanged = false
  }
  libraryOpen.value = false
  libraryError.value = ''
}
function switchLibraryMode(mode: 'select' | 'manage') {
  cancelLibraryTreeEdit()
  if (libraryChanged && mode === 'select') {
    libraryError.value = '请先保存站点库或取消修改，再返回选择编码'
    return
  }
  libraryMode.value = mode
  libraryError.value = ''
  libraryNotice.value = ''
}
function markLibraryDirty() {
  libraryChanged = true
  markDirty()
}
function toggleLibraryGroup(id: string) {
  expandedLibrary[id] = !expandedLibrary[id]
}
function cancelLibraryTreeEdit() {
  editingLibraryGroupId.value = ''
  editingLibraryItemId.value = ''
  addingLibraryItemGroupId.value = ''
  addingLibraryGroup.value = false
  libraryError.value = ''
}
function startAddingLibraryGroup() {
  cancelLibraryTreeEdit()
  newLibraryGroup.name = ''
  newLibraryGroup.prefix = ''
  newLibraryGroup.start = 1
  newLibraryGroup.step = 10
  addingLibraryGroup.value = true
}
function cancelAddingLibraryGroup() {
  addingLibraryGroup.value = false
  libraryError.value = ''
}
function libraryGroupUsedCount(group: any) {
  return (group.items || []).filter((item: any) => libraryUsedCodes.value.includes(String(item.code || '').toUpperCase())).length
}
function startEditLibraryGroup(group: any) {
  cancelLibraryTreeEdit()
  editingLibraryGroupId.value = group.id
  libraryGroupDraft.name = group.name || ''
  libraryGroupDraft.prefix = group.prefix || ''
  libraryGroupDraft.start = Number(group.start) || 1
  libraryGroupDraft.step = Number(group.step) || 10
}
function saveLibraryGroupEdit(group: any) {
  const name = String(libraryGroupDraft.name || '').trim()
  const prefix = String(libraryGroupDraft.prefix || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (!name || !prefix) { libraryError.value = '请填写分组名称和编码前缀'; return }
  if (sortedLibraryGroups.value.some((g: any) => g.id !== group.id && String(g.prefix || '').toUpperCase() === prefix)) {
    libraryError.value = '编码前缀已存在'; return
  }
  const oldPrefix = String(group.prefix || '').toUpperCase()
  const used = libraryGroupUsedCount(group)
  if (used && prefix !== oldPrefix) {
    libraryError.value = `该分组有 ${used} 个库项已使用，不能修改编码前缀`
    return
  }
  if (prefix !== oldPrefix) {
    (group.items || []).forEach((item: any) => {
      item.code = prefix + String(item.code || '').slice(oldPrefix.length)
    })
  }
  group.name = name
  group.prefix = prefix
  group.start = Math.max(1, Number(libraryGroupDraft.start) || 1)
  group.step = Math.max(1, Number(libraryGroupDraft.step) || 10)
  editingLibraryGroupId.value = ''
  libraryError.value = ''
  markLibraryDirty()
}
function startAddingLibraryItem(group: any) {
  cancelLibraryTreeEdit()
  libraryItemGroupId.value = group.id
  expandedLibrary[group.id] = true
  addingLibraryItemGroupId.value = group.id
  newTreeItem.name = ''
  newTreeItem.type = typeOptions.value[0]?.value || 'quality'
}
function addTreeLibraryItem(group: any) {
  libraryItemName.value = newTreeItem.name
  libraryItemType.value = newTreeItem.type
  libraryItemGroupId.value = group.id
  const before = (group.items || []).length
  addLibraryItem()
  if ((group.items || []).length > before) cancelLibraryTreeEdit()
}
function startEditLibraryItem(item: any) {
  cancelLibraryTreeEdit()
  editingLibraryItemId.value = item.id
  libraryItemDraft.name = item.name || ''
  libraryItemDraft.type = item.type || typeOptions.value[0]?.value || 'quality'
}
function saveLibraryItemEdit() {
  const target = allLibraryItems().find((item: any) => item.id === editingLibraryItemId.value)
  if (!target) { libraryError.value = '库项不存在'; return }
  const name = String(libraryItemDraft.name || '').trim()
  if (!name) { libraryError.value = '请填写库项名称'; return }
  target.name = name
  target.type = libraryItemDraft.type
  editingLibraryItemId.value = ''
  libraryError.value = ''
  markLibraryDirty()
}
function applyLibraryItem() {
  if (libraryMode.value !== 'select') {
    libraryError.value = '请先保存站点库或取消修改，再应用编码'
    return
  }
  if (!selected.value || !activeLibraryItem.value) {
    libraryError.value = '请先选择站点和站点库编码'
    return
  }
  const oldCode = String(selected.value.code || '')
  const item = activeLibraryItem.value
  const code = String(item.code || '').toUpperCase()
  const usedByOther = (config.value.stations || []).some((s: any) => s.id !== selected.value.id && String(s.code || '').toUpperCase() === code)
  if (usedByOther) {
    libraryError.value = `编码 ${code} 已被其他站点使用，请选择未使用的库编码`
    return
  }
  selected.value.code = code
  selected.value.name = item.name || oldCode
  selected.value.type = item.type || selected.value.type
  selected.value.description = item.description || ''
  if (isRepairLikeType(selected.value.type)) {
    const groupId = repairGroupId()
    if (groupId) selected.value.groupId = groupId
  }
  markDirty()
  libraryOpen.value = false
}
function isTypeUsed(value: string) {
  const inStations = (config.value?.stations || []).some((s: any) => s.type === value)
  const inLibrary = sortedLibraryGroups.value.some((group: any) => (group.items || []).some((item: any) => item.type === value))
  return inStations || inLibrary
}
function addStationType() {
  const label = newTypeLabel.value.trim()
  if (!label) { libraryError.value = '请输入站点类型名称'; return }
  const value = `type_${Date.now()}`
  config.value.options.stationTypes.push({ value, label })
  newTypeLabel.value = ''
  libraryError.value = ''
  markLibraryDirty()
}
function removeStationType(type: any) {
  if (isTypeUsed(type.value)) {
    libraryError.value = `类型“${type.label}”已被站点或库项使用，不能删除`
    return
  }
  config.value.options.stationTypes = config.value.options.stationTypes.filter((t: any) => t.value !== type.value)
  libraryError.value = ''
  markLibraryDirty()
}
function removeLibraryItem(item?: any) {
  const target = item || activeLibraryItem.value
  if (!target) return
  const code = String(target.code || '').toUpperCase()
  if (libraryUsedCodes.value.includes(code)) {
    libraryError.value = '该库编码已被站点使用，不能删除'
    return
  }
  const removed = target.id
  sortedLibraryGroups.value.forEach((group: any) => {
    group.items = (group.items || []).filter((i: any) => i.id !== removed)
  })
  if (libraryItemId.value === removed) libraryItemId.value = ''
  if (editingLibraryItemId.value === removed) editingLibraryItemId.value = ''
  libraryError.value = ''
  markLibraryDirty()
}
function removeLibraryGroup(group?: any) {
  const target = group || activeLibraryGroup.value
  if (!target) { libraryError.value = '请选择要删除的站点库分组'; return }
  if (editingLibraryGroupId.value === target.id) editingLibraryGroupId.value = ''
  const usedItems = (target.items || []).filter((item: any) => libraryUsedCodes.value.includes(String(item.code || '').toUpperCase()))
  if (usedItems.length) {
    libraryError.value = `分组“${target.name}”下有 ${usedItems.length} 个库项已被站点使用，不能删除`
    return
  }
  config.value.library = config.value.library.filter((g: any) => g.id !== target.id)
  libraryItemGroupId.value = sortedLibraryGroups.value[0]?.id || ''
  libraryItemId.value = ''
  delete expandedLibrary[target.id]
  libraryError.value = ''
  markLibraryDirty()
}
function addLibraryItem() {
  const group = sortedLibraryGroups.value.find((g: any) => g.id === libraryItemGroupId.value)
  if (!group) { libraryError.value = '请选择站点库分组'; return }
  const code = buildLibraryCode(group)
  const suffix = code.slice(String(group.prefix || '').length)
  const item = {
    id: newId('lib'), code,
    name: libraryItemName.value.trim() || `${group.name || '站点'}${suffix}`,
    type: libraryItemType.value,
    description: '',
  }
  group.items = [...(group.items || []), item]
  libraryItemId.value = item.id
  libraryItemName.value = ''
  libraryError.value = ''
  markLibraryDirty()
}
function addLibraryGroup() {
  const prefix = String(newLibraryGroup.prefix || '').toUpperCase().replace(/[^A-Z0-9]/g, '')
  if (!newLibraryGroup.name.trim() || !prefix) {
    libraryError.value = '请填写分组名称和编码前缀'
    return
  }
  const group = {
    id: newId('lib_grp'), name: newLibraryGroup.name.trim(), prefix,
    start: Math.max(1, Number(newLibraryGroup.start) || 1),
    step: Math.max(1, Number(newLibraryGroup.step) || 10),
    description: '', order: sortedLibraryGroups.value.length + 1, items: [],
  }
  config.value.library = [...sortedLibraryGroups.value, group]
  libraryItemGroupId.value = group.id
  expandedLibrary[group.id] = true
  addingLibraryGroup.value = false
  newLibraryGroup.name = ''
  newLibraryGroup.prefix = ''
  newLibraryGroup.start = 1
  newLibraryGroup.step = 10
  libraryError.value = ''
  markLibraryDirty()
}
async function saveLibrary() {
  if (!libraryChanged) { libraryOpen.value = false; return }
  const ok = await save('站点库已保存')
  if (ok) {
    libraryChanged = false
    libraryOpen.value = false
  }
}
function migrateInvalidCodes() {
  const valid = new Set(allLibraryItems().map((item: any) => String(item.code || '').toUpperCase()))
  const used = new Set(libraryUsedCodes.value)
  let changed = 0
  ;(config.value.stations || []).forEach((station: any) => {
    const code = String(station.code || '').toUpperCase()
    if (valid.has(code)) return
    const oldName = station.name
    const item = allLibraryItems().find((entry: any) => !used.has(String(entry.code || '').toUpperCase()))
    if (!item) return
    station.code = String(item.code || '').toUpperCase()
    if (!station.name || station.name === code) station.name = item.name
    station.type = item.type || station.type
    used.add(station.code)
    changed += 1
  })
  return changed
}
function addStation() {
  const picked = defaultLibraryItem()
  if (!picked) {
    error.value = '站点库已全部使用，请先在站点库中新增库项'
    openLibrary('manage')
    return
  }
  const type = String(picked.type || 'normal')
  const groupId = isRepairLikeType(type) ? (repairGroupId() || sortedGroups.value[0]?.id) : sortedGroups.value[0]?.id
  if (!groupId) { error.value = '请先新增分组'; return }
  const order = sortedStations.value.length + 1
  const code = String(picked.code || '').toUpperCase()
  const station = {
    id: newId('station'), code,
    name: picked.name || code, type, groupId, order,
    enabled: true, description: '', workInstruction: '', params: [], paramFiles: [], failCodes: [], returnStationId: '',
  }
  config.value.stations.push(station)
  selectedId.value = station.id
  markDirty()
}
function formatFileSize(size: number) {
  const n = Number(size) || 0
  return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)}MB` : `${Math.max(1, Math.round(n / 1024))}KB`
}
async function onParamFileUploaded(payload: { file: File; meta: any; prepared: any }) {
  if (!selected.value) return
  paramFileError.value = ''
  paramFileNotice.value = ''
  selected.value.paramFiles = [...(selected.value.paramFiles || []), payload.meta]
  paramFileNotice.value = `${payload.file.name} 已作为参考附件上传，不参与参数解析`
  markDirty()
}
async function downloadParamFile(file: any) {
  if (!selected.value) return
  try {
    const blob = await api.downloadParamFile(selected.value.id, file.id)
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = file.name || file.id
    link.click()
    URL.revokeObjectURL(url)
  } catch (error: any) {
    paramFileError.value = error.message || '下载失败'
  }
}
async function deleteParamFile(file: any) {
  if (!selected.value) return
  try {
    await api.deleteParamFile(selected.value.id, file.id)
    selected.value.paramFiles = (selected.value.paramFiles || []).filter((item: any) => item.id !== file.id)
    paramFileNotice.value = '附件已移除，请点击“保存设计”生效'
    markDirty()
  } catch (error: any) {
    paramFileError.value = error.message || '移除失败'
  }
}
function addParam() {
  selected.value.params = selected.value.params || []
  selected.value.params.push({ key: `param_${selected.value.params.length + 1}`, label: '新参数', value: '', unit: '', required: false })
  markDirty()
}
function addFailCode() {
  selected.value.failCodes = selected.value.failCodes || []
  selected.value.failCodes.push({ code: `F${String(selected.value.failCodes.length + 1).padStart(3, '0')}`, name: '新不良代码' })
  markDirty()
}
function canMove(delta: number) {
  const index = sortedStations.value.findIndex((s: any) => s.id === selectedId.value)
  return index >= 0 && index + delta >= 0 && index + delta < sortedStations.value.length
}
function move(delta: number) {
  const list = sortedStations.value
  const index = list.findIndex((s: any) => s.id === selectedId.value)
  const target = index + delta
  if (index < 0 || target < 0 || target >= list.length) return
  const current = config.value.stations.find((s: any) => s.id === list[index].id)
  const other = config.value.stations.find((s: any) => s.id === list[target].id)
  const currentOrder = current.order
  current.order = other.order
  other.order = currentOrder
  markDirty()
}
function removeStation() {
  if (!selected.value) return
  if (!window.confirm(`确认删除站点 ${selected.value.code}？`)) return
  const removedId = selected.value.id
  config.value.stations = config.value.stations.filter((s: any) => s.id !== removedId)
  config.value.stations.forEach((s: any) => { if (s.returnStationId === removedId) s.returnStationId = '' })
  if (config.value.settings.repairStationId === removedId) config.value.settings.repairStationId = ''
  selectedId.value = ''
  markDirty()
}
function removeDragListeners() {
  window.removeEventListener('pointermove', onDragMove)
  window.removeEventListener('pointerup', onDragEnd)
  window.removeEventListener('pointercancel', onDragEnd)
}
function startDrag(event: PointerEvent, station: any) {
  if (saving.value || drag.active) return
  dragPointerId = event.pointerId
  dragHandle = event.currentTarget as HTMLElement
  drag.active = true
  drag.id = station.id
  drag.section = stationSectionKey(station)
  drag.targetId = ''
  drag.position = ''
  drag.wasDirty = dirty.value
  drag.changed = false
  window.addEventListener('pointermove', onDragMove, { passive: false })
  window.addEventListener('pointerup', onDragEnd)
  window.addEventListener('pointercancel', onDragEnd)
}
function onDragMove(event: PointerEvent) {
  if (!drag.active || event.pointerId !== dragPointerId) return
  event.preventDefault()
  const el = document.elementFromPoint(event.clientX, event.clientY)?.closest('[data-station-card]') as HTMLElement | null
  const targetId = el?.dataset.stationCard || ''
  const target = sortedStations.value.find((s: any) => s.id === targetId)
  if (!el || !targetId || targetId === drag.id || !target || stationSectionKey(target) !== drag.section) {
    drag.targetId = ''
    drag.position = ''
    return
  }
  const rect = el.getBoundingClientRect()
  const after = window.innerWidth <= 768
    ? event.clientY > rect.top + rect.height / 2
    : event.clientX > rect.left + rect.width / 2
  drag.targetId = targetId
  drag.position = after ? 'after' : 'before'
  const list = stationsBySection(drag.section).slice()
  const from = list.findIndex((s: any) => s.id === drag.id)
  const targetIndex = list.findIndex((s: any) => s.id === targetId)
  if (from < 0 || targetIndex < 0) return
  const [moved] = list.splice(from, 1)
  let insert = targetIndex + (after ? 1 : 0)
  if (from < insert) insert -= 1
  insert = Math.max(0, Math.min(list.length, insert))
  list.splice(insert, 0, moved)
  const other = drag.section === 'repair' ? mainStations.value : repairStations.value
  const ordered = drag.section === 'repair' ? [...other, ...list] : [...list, ...other]
  ordered.forEach((s: any, index: number) => { s.order = index + 1 })
  config.value.stations = ordered
  drag.changed = true
  markDirty()
}
function onDragEnd(event: PointerEvent) {
  if (!drag.active || event.pointerId !== dragPointerId) return
  removeDragListeners()
  if (dragHandle?.hasPointerCapture?.(dragPointerId)) dragHandle.releasePointerCapture(dragPointerId)
  const wasDirty = drag.wasDirty
  const changed = drag.changed
  dragHandle = null
  dragPointerId = null
  drag.active = false
  drag.id = ''
  drag.section = ''
  drag.targetId = ''
  drag.position = ''
  if (!changed) return
  if (!wasDirty) void save('站点顺序已保存')
  else notice.value = '站点顺序已调整，请保存设计'
}
async function reload() {
  loading.value = true
  error.value = ''
  try {
    config.value = await api.processDesign()
    const migrated = migrateInvalidCodes()
    const wanted = String(route.query.station || '').trim().toUpperCase()
    const matched = wanted
      ? sortedStations.value.find((s: any) => String(s.code || '').toUpperCase() === wanted)
      : null
    selectedId.value = matched?.id || sortedStations.value[0]?.id || ''
    dirty.value = migrated > 0
    notice.value = migrated > 0 ? `已将 ${migrated} 个非站点库编码替换为默认库编码，请保存设计` : ''
  } catch (e: any) {
    error.value = e.message || '加载工艺站点设计失败'
  } finally {
    loading.value = false
  }
}
async function save(message = '站点设计已保存') {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    config.value = await api.saveProcessDesign(config.value)
    dirty.value = false
    notice.value = message
    return true
  } catch (e: any) {
    error.value = e.message || '保存失败'
    return false
  } finally {
    saving.value = false
  }
}
onMounted(reload)
onBeforeUnmount(removeDragListeners)
</script>

<style scoped>
.method-page { max-width: 1500px; margin: 0 auto; }
.temporarily-hidden { display: none !important; }
.head { display: flex; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
.row { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-start; }
.design-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr) 340px; gap: 12px; align-items: start; }
.panel { background: var(--white); border: 1px solid var(--line); border-radius: 8px; padding: 12px; min-width: 0; }
.panel-head { display: flex; justify-content: space-between; gap: 8px; align-items: center; margin-bottom: 10px; }
.group-block { margin-bottom: 12px; }
.group-row { display: flex; align-items: center; gap: 8px; padding: 4px 2px; font-size: 13px; }
.count { color: var(--muted); font-size: 11px; }
.station-node { display: grid; grid-template-columns: 52px minmax(0,1fr) auto; gap: 6px; width: 100%; align-items: center; border: 1px solid transparent; background: transparent; border-radius: 6px; padding: 7px 6px; cursor: pointer; text-align: left; color: var(--ink); font-family: inherit; font-size: 12px; }
.station-node:hover, .station-node.active { background: var(--tech-blue-soft); border-color: var(--tech-blue-line); }
.station-node.disabled { opacity: .55; }
.node-code { color: var(--tech-blue); font-weight: 700; }
.node-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.node-type { color: var(--muted); font-size: 10px; }
.canvas { border: 1px dashed var(--line); border-radius: 8px; padding: 10px; background: #fafbfc; min-height: 220px; }
.station-section + .station-section { margin-top: 14px; border-top: 1px dashed var(--line); padding-top: 12px; }
.section-title { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
.section-title b { font-size: 13px; }
.station-card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; align-items: start; }
.section-repair .station-card-grid { grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); }
.station-card { position: relative; border: 1px solid var(--line); border-radius: 9px; background: #fff; padding: 11px; min-width: 0; cursor: pointer; box-shadow: 0 1px 2px rgba(30,34,40,.04); transition: opacity .14s, transform .14s, border-color .14s, box-shadow .14s; }
.station-card:hover { border-color: var(--tech-blue-line); transform: translateY(-1px); box-shadow: 0 4px 14px rgba(46,111,232,.08); }
.station-card.active { border-color: var(--tech-blue); box-shadow: 0 0 0 2px var(--tech-blue-soft); }
.station-card.disabled { opacity: .58; }
.station-card.dragging { opacity: .45; transform: scale(.97); border-style: dashed; border-color: var(--tech-blue); }
.station-card.drop-before { box-shadow: -4px 0 0 var(--tech-blue), 0 0 0 2px var(--tech-blue-soft); }
.station-card.drop-after { box-shadow: 4px 0 0 var(--tech-blue), 0 0 0 2px var(--tech-blue-soft); }
.card-top { display: flex; align-items: center; gap: 7px; min-width: 0; }
.drag-handle { color: var(--muted); cursor: grab; font-size: 17px; line-height: 1; padding: 2px 3px; border-radius: 4px; touch-action: none; user-select: none; }
.drag-handle:hover { background: var(--tech-blue-soft); color: var(--tech-blue); }
.drag-handle:active { cursor: grabbing; }
.order-badge { display: inline-grid; place-items: center; width: 20px; height: 20px; border-radius: 50%; background: var(--tech-blue-soft); color: var(--tech-blue); font-size: 11px; font-weight: 700; flex: none; }
.card-code { color: var(--tech-blue); font-weight: 700; font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.disabled-tag { margin-left: auto; border-radius: 4px; background: var(--red-soft); color: var(--red); font-size: 10px; padding: 2px 5px; }
.card-name { display: block; margin: 9px 0 7px; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-detail-link { margin-top: -2px; margin-bottom: 6px; }
.code-picker { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 5px; align-items: center; }
.code-picker input[readonly] { background: #f7f8fa; color: var(--ink); font-weight: 700; }
.card-meta { display: flex; gap: 5px; flex-wrap: wrap; }
.type-tag, .group-tag { border-radius: 4px; padding: 3px 6px; font-size: 10px; }
.type-tag { background: var(--tech-blue-soft); color: var(--tech-blue); }
.group-tag { background: #f3f4f6; color: var(--muted); }
.card-stats { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 9px; padding-top: 7px; border-top: 1px dashed var(--line); color: var(--muted); font-size: 10px; }
.empty-line { color: var(--muted); font-size: 12px; padding: 10px; }
.settings-strip { display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 8px; margin-top: 12px; }
.settings-strip label, .form-grid label, .field label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
input, select, textarea { width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 7px 8px; font-family: inherit; color: var(--ink); background: #fff; }
.check-line { display: flex !important; align-items: center; gap: 6px; }
.check-line input { width: auto; }
.relation-card { margin-top: 12px; border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
.relation-card > b { font-size: 13px; }
.relation-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; margin-top: 8px; }
.relation-grid > div { border-top: 1px dashed var(--line); padding-top: 6px; }
.relation-grid label, .relation-grid small { display: block; color: var(--muted); font-size: 11px; }
.relation-grid b { font-size: 12px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
.field { margin-top: 10px; }
.section-head { display: flex; justify-content: space-between; align-items: center; margin: 12px 0 6px; font-size: 13px; }
.param-list { display: grid; gap: 5px; }
.param-row, .param-config-row { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 4px; }
.param-config-row { grid-template-columns: repeat(3, minmax(0,1fr)); align-items: center; }
.param-head.param-config-row { font-size: 10px; color: var(--muted); }
.param-row input { min-width: 0; }
.param-required { display: flex; align-items: center; gap: 4px; font-size: 11px; color: var(--muted); white-space: nowrap; }
.param-required input { width: auto; }
.param-rule { border: 1px dashed var(--line); border-radius: 6px; padding: 7px 9px; color: var(--muted); font-size: 11px; line-height: 1.6; margin-bottom: 8px; }
.param-file-list { display: grid; gap: 4px; margin: 8px 0; }
.param-file-row { display: grid; grid-template-columns: minmax(0,1fr) auto auto auto; gap: 8px; align-items: center; border: 1px solid var(--line); border-radius: 6px; padding: 6px 8px; font-size: 11px; }
.param-file-row small { color: var(--muted); }
.empty-box { border: 1px dashed var(--line); border-radius: 6px; padding: 10px; color: var(--muted); font-size: 12px; text-align: center; }
.empty-box.tall { padding: 50px 10px; }
.detail-actions { display: flex; gap: 6px; margin-top: 14px; }
.danger-link { color: var(--red); }
.btn.full { width: 100%; margin-top: 8px; }
.link { border: 0; background: transparent; cursor: pointer; padding: 0; font-size: 11px; color: var(--tech-blue); }
.mini { color: var(--muted); font-size: 11px; }
.msg { padding: 9px 12px; border-radius: 5px; margin-bottom: 10px; }
.msg.err { background: var(--red-soft); color: var(--red); }
.msg.ok { background: var(--green-soft); color: var(--green); }
.modal-mask { position: fixed; inset: 0; z-index: 100; display: flex; align-items: center; justify-content: center; padding: 16px; background: rgba(4,8,18,.65); }
.modal { width: 100%; max-width: 920px; max-height: min(92dvh, 900px); overflow: auto; background: var(--white); border-radius: 10px; padding: 18px; }
.station-edit-modal { width: 100%; max-width: min(92vw, 720px); }
.station-edit-form { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
.station-edit-form label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.station-edit-form label.full, .station-edit-form .modal-foot.full, .station-edit-form .relation-block.full, .station-edit-form .fail-code-block.full { grid-column: 1 / -1; }
.station-edit-form .check-line { display: flex; align-items: center; gap: 7px; }
.relation-block { border-top: 1px solid var(--line); padding-top: 10px; margin-top: 2px; }
.relation-edit-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-top: 8px; }
.relation-edit-grid > div { border: 1px solid var(--line); border-radius: 8px; padding: 7px; min-width: 0; }
.relation-edit-grid > div > span { display: block; color: var(--muted); font-size: 11px; margin-bottom: 6px; }
.option-list { display: grid; gap: 5px; max-height: 116px; overflow: auto; }
.option-list label { display: flex; align-items: flex-start; gap: 5px; color: var(--ink); font-size: 11px; line-height: 1.35; cursor: pointer; }
.option-list input { width: auto; margin-top: 2px; }
.empty-mini { color: var(--muted); font-size: 11px; padding: 8px 2px; }
.fail-code-block { border-top: 1px solid var(--line); padding-top: 10px; margin-top: 2px; }
.edit-fail-list { display: grid; gap: 6px; margin-top: 8px; }
.edit-fail-row { display: grid; grid-template-columns: minmax(0, .7fr) minmax(0, 1fr) minmax(0, 1.2fr) auto; gap: 6px; align-items: center; }
.defect-mask { z-index: 120; }
.defect-modal { max-width: min(96vw, 1100px); }
.defect-layout { display: grid; grid-template-columns: minmax(0, 1.5fr) minmax(260px, .7fr); gap: 14px; margin-top: 10px; }
.defect-list { min-width: 0; }
.defect-table-wrap { max-height: 52vh; overflow: auto; border: 1px solid var(--line); border-radius: 8px; margin-top: 8px; }
.defect-form-panel { border: 1px solid var(--line); border-radius: 8px; padding: 10px; display: grid; gap: 8px; align-content: start; }
.defect-form-panel label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.defect-form-panel input, .defect-form-panel select, .defect-form-panel textarea { width: 100%; }
.defect-import { border-top: 1px solid var(--line); padding-top: 8px; display: grid; gap: 6px; font-size: 12px; }
.empty-box { border: 1px dashed var(--line); border-radius: 6px; padding: 10px; text-align: center; color: var(--muted); font-size: 11px; margin-top: 8px; }
@media (max-width: 768px) { .station-edit-modal { max-width: 94vw; } .station-edit-form { grid-template-columns: 1fr; } }
@media (max-width: 600px) { .relation-edit-grid { grid-template-columns: 1fr; } .option-list { max-height: 92px; } .edit-fail-row { grid-template-columns: 1fr; } .defect-layout { grid-template-columns: 1fr; } }
.library-layout { display: grid; grid-template-columns: minmax(260px, 1fr) minmax(320px, 1.1fr); gap: 14px; }
.library-tree { border: 1px solid var(--line); border-radius: 8px; padding: 8px; max-height: 58vh; overflow: auto; }
.tree-toolbar { display: flex; align-items: center; justify-content: space-between; padding: 2px 4px 8px; border-bottom: 1px solid var(--line); }
.library-group + .library-group { margin-top: 6px; border-top: 1px dashed var(--line); padding-top: 6px; }
.library-group-head { display: flex; align-items: center; gap: 4px; width: 100%; border: 0; background: transparent; padding: 6px; font-family: inherit; font-size: 13px; color: var(--ink); text-align: left; }
.library-group-head .tree-main { flex: 1; min-width: 0; }
.library-group-head small { color: var(--muted); }
.tree-main { display: grid; grid-template-columns: 60px minmax(0,1fr) auto; gap: 6px; align-items: center; flex: 1; min-width: 0; border: 0; background: transparent; padding: 0; cursor: pointer; text-align: left; font-family: inherit; font-size: 12px; color: var(--ink); }
.library-group-head .tree-main { display: flex; flex-wrap: wrap; }
.library-items { padding-left: 18px; }
.library-item { display: flex; align-items: center; gap: 4px; width: 100%; border: 1px solid transparent; background: transparent; border-radius: 6px; padding: 3px 5px; text-align: left; font-family: inherit; font-size: 12px; color: var(--ink); }
.library-item:hover, .library-item.active { background: var(--tech-blue-soft); border-color: var(--tech-blue-line); }
.library-item small { color: var(--muted); font-size: 10px; }
.library-item.used small { color: var(--tech-blue); }
.tree-edit-box { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 5px; padding: 6px; margin: 4px 0; background: var(--tech-blue-soft); border-radius: 6px; }
.tree-edit-box > div { grid-column: 1 / -1; display: flex; gap: 6px; justify-content: flex-end; }
.tree-edit-box input, .tree-edit-box select { width: 100%; min-width: 0; border: 1px solid var(--line); border-radius: 5px; padding: 5px 6px; font-family: inherit; font-size: 11px; background: var(--white); color: var(--ink); }
.library-form { min-width: 0; }
.library-form h4 { font-size: 13px; margin: 12px 0 7px; }
.library-form h4:first-child { margin-top: 0; }
.library-detail, .library-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 8px; }
.library-form-grid .library-actions { grid-column: 1 / -1; margin-top: 0; }
.library-detail label, .library-form-grid label { display: grid; gap: 4px; color: var(--muted); font-size: 11px; }
.library-detail b { font-size: 13px; padding: 7px 0; }
.library-actions { display: flex; gap: 6px; margin-top: 8px; }
.type-list { display: grid; gap: 6px; }
.type-row { display: grid; grid-template-columns: 92px minmax(0,1fr) auto; gap: 6px; align-items: center; }
.type-row > span { color: var(--muted); font-size: 10px; overflow: hidden; text-overflow: ellipsis; }
.type-add { display: grid; grid-template-columns: minmax(0,1fr) auto; gap: 6px; margin-top: 2px; }
.code-preview { border: 1px dashed var(--line); border-radius: 6px; padding: 7px 9px; align-self: end; font-size: 11px; color: var(--muted); }
.code-preview b { color: var(--tech-blue); }
@media (max-width: 1180px) { .design-layout { grid-template-columns: 220px minmax(0,1fr); } .detail-panel { grid-column: 1 / -1; } }
@media (max-width: 900px) { .head { flex-direction: column; } .design-layout { grid-template-columns: 1fr; } .settings-strip { grid-template-columns: repeat(2, minmax(0,1fr)); } }
@media (max-width: 768px) {
  .library-layout, .library-detail, .library-form-grid { grid-template-columns: 1fr; }
  .type-row, .type-add { grid-template-columns: 1fr; }
  .library-tree { max-height: 36vh; }
  .station-card-grid { grid-template-columns: 1fr; }
  .station-card.drop-before { box-shadow: 0 -4px 0 var(--tech-blue), 0 0 0 2px var(--tech-blue-soft); }
  .station-card.drop-after { box-shadow: 0 4px 0 var(--tech-blue), 0 0 0 2px var(--tech-blue-soft); }
}
@media (max-width: 768px) {
  .param-config-row { grid-template-columns: 1fr 1fr; }
  .param-file-row { grid-template-columns: 1fr auto; }
  .design-layout, .detail-panel, .panel, .resumable-uploader, .drop-zone { min-width: 0; width: 100%; max-width: 100%; box-sizing: border-box; }
}
@media (max-width: 480px) { .settings-strip, .relation-grid, .form-grid, .param-row, .param-config-row { grid-template-columns: 1fr; } }
</style>
