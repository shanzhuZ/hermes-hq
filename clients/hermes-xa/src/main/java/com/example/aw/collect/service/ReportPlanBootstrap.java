package com.example.aw.collect.service;

import com.example.aw.collect.mapper.CollectTaskMapper;
import com.example.aw.collect.stream.ThoughtStreamHub;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * 04 写报：Java 推「思考中 → 规划六大节点」并收口 step_plan（v3）。
 */
@Service
public class ReportPlanBootstrap {

    private static final Logger log = LoggerFactory.getLogger(ReportPlanBootstrap.class);

    private static final long THINKING_HOLD_MS = 1800L;
    private static final long PLANNING_HOLD_MS = 1600L;

    @Autowired
    private ThoughtStreamHub thoughtStreamHub;

    @Autowired
    private CollectTaskMapper collectTaskMapper;

    public void beginPlanStream(String taskId) {
        if (taskId == null || taskId.trim().isEmpty()) {
            return;
        }
        thoughtStreamHub.open(taskId);
        collectTaskMapper.updateStepStatus(
                taskId, ReportTaskCreateService.STEP_PLAN, "running", "思考中…");

        Map<String, Object> started = new LinkedHashMap<String, Object>();
        started.put("taskId", taskId);
        started.put("content", "思考中…");
        thoughtStreamHub.publish(taskId, "plan.started", started);

        publishThinking(taskId, "思考中…");
        log.info("04 规划开场已推送（思考中） taskId={}", taskId);
    }

    public void finishPlanStreamPaced(String taskId) {
        if (taskId == null || taskId.trim().isEmpty()) {
            return;
        }
        sleepQuiet(THINKING_HOLD_MS);

        String planning = "思考中…\n\n任务规划中…\n正在为本任务规划执行节点（输入分析 + 6 个业务阶段）…";
        publishThinkingSafe(taskId, planning);

        sleepQuiet(PLANNING_HOLD_MS);

        List<Map<String, Object>> phases = fixedPhases();
        StringBuilder listed = new StringBuilder();
        listed.append(planning).append("\n\n");
        listed.append("已规划好本任务执行节点：\n");
        for (Map<String, Object> p : phases) {
            listed.append(p.get("title")).append("\n");
        }
        listed.append("\n规划完成。");
        String listedText = listed.toString();

        String planMsg = "已规划好节点：0.输入分析；1.主账号采集；2.Maigret跨平台；3.账号认定；"
                + "4.公开信息检索；5.全账号发文；6.报告生成";
        collectTaskMapper.updateStepStatus(
                taskId, ReportTaskCreateService.STEP_PLAN, "completed", planMsg);

        publishThinkingSafe(taskId, listedText);

        Map<String, Object> ready = new LinkedHashMap<String, Object>();
        ready.put("taskId", taskId);
        ready.put("phases", phases);
        ready.put("content", "已规划好输入分析与六大执行阶段（待开始执行）");
        ready.put("gatePhase", null);
        ready.put("executionStarted", Boolean.FALSE);
        try {
            thoughtStreamHub.publish(taskId, "plan.ready", ready);
        } catch (Exception e) {
            log.warn("plan.ready 推送失败（step_plan 已 completed） taskId={}: {}", taskId, e.getMessage());
        }

        log.info("04 规划流慢推完成（业务节点仍 pending） taskId={}", taskId);
    }

    private void publishThinking(String taskId, String content) {
        Map<String, Object> delta = new LinkedHashMap<String, Object>();
        delta.put("taskId", taskId);
        delta.put("content", content);
        thoughtStreamHub.publish(taskId, "assistant.delta", delta);

        Map<String, Object> progress = new LinkedHashMap<String, Object>();
        progress.put("taskId", taskId);
        progress.put("content", content);
        progress.put("toolName", "_thinking");
        thoughtStreamHub.publish(taskId, "tool.progress", progress);
    }

    private void publishThinkingSafe(String taskId, String content) {
        try {
            publishThinking(taskId, content);
        } catch (Exception e) {
            log.warn("规划思考文案推送失败 taskId={}: {}", taskId, e.getMessage());
        }
    }

    private static void sleepQuiet(long ms) {
        if (ms <= 0L) {
            return;
        }
        try {
            Thread.sleep(ms);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static List<Map<String, Object>> fixedPhases() {
        List<Map<String, Object>> phases = new ArrayList<Map<String, Object>>();
        phases.add(phase(0, ReportTaskCreateService.PHASE_INTAKE, "0. 输入分析"));
        phases.add(phase(1, ReportTaskCreateService.PHASE_LOCK_TARGET, "1. 主账号采集"));
        phases.add(phase(2, ReportTaskCreateService.PHASE_DISCOVERY, "2. Maigret 跨平台检索"));
        phases.add(phase(3, ReportTaskCreateService.PHASE_IDENTITY, "3. 账号认定"));
        phases.add(phase(4, ReportTaskCreateService.PHASE_WEB_INTEL, "4. 公开信息检索"));
        phases.add(phase(5, ReportTaskCreateService.PHASE_CONTENT, "5. 全账号发文采集"));
        phases.add(phase(6, ReportTaskCreateService.PHASE_REPORT, "6. 报告生成"));
        return phases;
    }

    private static Map<String, Object> phase(int order, String key, String title) {
        Map<String, Object> m = new LinkedHashMap<String, Object>();
        m.put("order", Integer.valueOf(order));
        m.put("phaseKey", key);
        m.put("title", title);
        return m;
    }
}
