package com.example.aw.collect.service;

import com.alibaba.fastjson.JSON;
import com.example.aw.collect.SourceTag;
import com.example.aw.collect.mapper.CollectTaskMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.HashMap;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * 04 公开资料核查写报（hermes-hq）— 预建任务：step_plan + 六大阶段壳 + 业务子步。
 * <p>
 * v3：主账号 → Maigret → 账号认定 → 公开信息检索 → 全账号发文 → 八章报告。
 */
@Service
public class ReportTaskCreateService implements TaskCreateService {

    public static final String STEP_PLAN = "step_plan";
    public static final String PHASE_LOCK_TARGET = "phase_lock_target";
    public static final String PHASE_DISCOVERY = "phase_discovery";
    public static final String PHASE_IDENTITY = "phase_identity";
    /** @deprecated 兼容旧名，等同 {@link #PHASE_IDENTITY} */
    public static final String PHASE_COLLISION = PHASE_IDENTITY;
    public static final String PHASE_WEB_INTEL = "phase_web_intel";
    /** @deprecated 旧「账号采集」壳，树上已改为认定内候选主页 */
    public static final String PHASE_ACCOUNT_COLLECT = "phase_account_collect";
    public static final String PHASE_CONTENT = "phase_content";
    /** @deprecated 方案 A 专题壳，已移除 */
    public static final String PHASE_ANALYSIS = "phase_analysis";
    public static final String PHASE_REPORT = "phase_report";

    @Autowired
    private CollectTaskMapper collectTaskMapper;

    @Override
    public String dbTaskType() {
        return "account_report";
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public String createPendingTask(String taskId, String sessionId, String userMessage, String payloadJson) {
        if (taskId == null || taskId.trim().isEmpty()) {
            throw new IllegalArgumentException("taskId 不能为空");
        }
        if (sessionId == null || sessionId.trim().isEmpty()) {
            throw new IllegalArgumentException("sessionId 不能为空");
        }
        if (userMessage == null || userMessage.trim().isEmpty()) {
            throw new IllegalArgumentException("message 不能为空");
        }
        if (!isReportIntent(userMessage)) {
            throw new IllegalArgumentException("非画像写报意图消息，无法创建任务");
        }

        Map<String, Object> exists = collectTaskMapper.selectTaskById(taskId);
        if (exists != null && !exists.isEmpty()) {
            return taskId;
        }

        Map<String, Object> active = collectTaskMapper.selectActiveTaskBySessionId(sessionId);
        if (active != null && !active.isEmpty()) {
            throw new IllegalStateException(
                    "会话 " + sessionId + " 已有进行中的任务 " + active.get("task_id") + "，请等待结束后再发起");
        }

        Map<String, Object> seed = buildSeedJson(userMessage);
        String seedJson = JSON.toJSONString(seed);
        collectTaskMapper.insertTask(taskId, sessionId, dbTaskType(), 1, seedJson);
        String clipped = userMessage.length() > 65535 ? userMessage.substring(0, 65535) : userMessage;
        collectTaskMapper.insertUserDialogue(taskId, sessionId, clipped, payloadJson);
        insertReportSteps(taskId, stringVal(seed.get("platform")));
        return taskId;
    }

    private boolean isReportIntent(String message) {
        Pattern p = Pattern.compile(
                "(account-intelligence-report|account-intelligence-profile|画像写报|写报.*?"
                        + "(推特|twitter|微博|weibo|youtube|bilibili|"
                        + "instagram|tiktok|telegram|facebook|github|linkedin|@))",
                Pattern.CASE_INSENSITIVE);
        return p.matcher(message).find();
    }

    private Map<String, Object> buildSeedJson(String message) {
        Map<String, Object> seed = new HashMap<String, Object>();
        seed.put("platform", "twitter");
        String text = stripSkillPrefix(message);
        Pattern platformHint = Pattern.compile(
                "(推特|twitter|微博|weibo|youtube|bilibili|instagram|\\bins\\b|\\big\\b|"
                        + "tiktok|telegram|\\btg\\b|facebook|\\bfb\\b|脸书|github|linkedin)",
                Pattern.CASE_INSENSITIVE);
        Matcher pm = platformHint.matcher(text);
        if (pm.find()) {
            String token = pm.group(1).toLowerCase();
            if ("微博".equals(token) || "weibo".equals(token)) {
                seed.put("platform", "weibo");
            } else if ("youtube".equals(token)) {
                seed.put("platform", "youtube");
            } else if ("bilibili".equals(token)) {
                seed.put("platform", "bilibili");
            } else if ("instagram".equals(token) || "ins".equals(token) || "ig".equals(token)) {
                seed.put("platform", "instagram");
            } else if ("tiktok".equals(token)) {
                seed.put("platform", "tiktok");
            } else if ("telegram".equals(token) || "tg".equals(token)) {
                seed.put("platform", "telegram");
            } else if ("facebook".equals(token) || "fb".equals(token) || "脸书".equals(token)) {
                seed.put("platform", "facebook");
            } else if ("github".equals(token)) {
                seed.put("platform", "github");
            } else if ("linkedin".equals(token)) {
                seed.put("platform", "linkedin");
            }
        }
        Matcher hm = Pattern.compile("@([A-Za-z0-9_\\.]+)").matcher(text);
        if (hm.find()) {
            seed.put("account_handle", hm.group(1));
            seed.put("account_hint", hm.group(1));
        } else {
            String hint = text.trim();
            if (hint.length() > 128) {
                hint = hint.substring(0, 128);
            }
            seed.put("account_hint", hint);
        }
        seed.put("parse_status", "pending");
        return seed;
    }

    private static String stripSkillPrefix(String message) {
        if (message == null) {
            return "";
        }
        return message.trim().replaceFirst(
                "(?i)^(account-intelligence-collect|account-expansion|account-intelligence-expand|"
                        + "account-intelligence-verification|account-intelligence-verify|"
                        + "account-intelligence-report|account-intelligence-profile)\\b\\s*",
                "");
    }

    private void insertReportSteps(String taskId, String seedPlatform) {
        collectTaskMapper.insertPhaseStep(taskId, STEP_PLAN, null, 5, "0", "制定执行计划",
                SourceTag.jsonForStep(STEP_PLAN));

        collectTaskMapper.insertPhaseStep(taskId, PHASE_LOCK_TARGET, STEP_PLAN, 100, "1", "1. 主账号采集",
                SourceTag.jsonForStep(PHASE_LOCK_TARGET));
        collectTaskMapper.insertPhaseStep(taskId, PHASE_DISCOVERY, STEP_PLAN, 200, "2", "2. Maigret 跨平台检索",
                SourceTag.jsonForStep(PHASE_DISCOVERY));
        collectTaskMapper.insertPhaseStep(taskId, PHASE_IDENTITY, STEP_PLAN, 300, "3", "3. 账号认定",
                SourceTag.jsonForStep(PHASE_IDENTITY));
        collectTaskMapper.insertPhaseStep(taskId, PHASE_WEB_INTEL, STEP_PLAN, 400, "4", "4. 公开信息检索",
                SourceTag.jsonForStep(PHASE_WEB_INTEL));
        collectTaskMapper.insertPhaseStep(taskId, PHASE_CONTENT, STEP_PLAN, 500, "5", "5. 全账号发文采集",
                SourceTag.jsonForStep(PHASE_CONTENT));
        collectTaskMapper.insertPhaseStep(taskId, PHASE_REPORT, STEP_PLAN, 600, "6", "6. 报告生成",
                SourceTag.jsonForStep(PHASE_REPORT));

        collectTaskMapper.insertPhaseStep(
                taskId, "step1_seed", PHASE_LOCK_TARGET, 110, "1.1",
                seedAgentTitle(seedPlatform), SourceTag.jsonForStep("step1_seed", seedPlatform));
        collectTaskMapper.insertPhaseStep(
                taskId, "step2_maigret", PHASE_DISCOVERY, 210, "2.1",
                "Maigret Agent 跨平台账号检索", SourceTag.jsonForStep("step2_maigret"));
        collectTaskMapper.insertPhaseStep(
                taskId, "step3_identity", PHASE_IDENTITY, 310, "3.1",
                "账号认定 Agent", SourceTag.jsonForStep("step3_identity"));
        collectTaskMapper.insertPhaseStep(
                taskId, "step3_profiles", PHASE_IDENTITY, 320, "3.2",
                "候选主页采集（认定佐证）", SourceTag.jsonForStep("step3_profiles"));
        collectTaskMapper.insertPhaseStep(
                taskId, "step4_osint_web", PHASE_WEB_INTEL, 410, "4.1",
                "网页检索 Agent 公开信息备料", SourceTag.jsonForStep("step4_osint_web"));
        collectTaskMapper.insertPhaseStep(
                taskId, "step5_posts", PHASE_CONTENT, 510, "5.1",
                "跨平台发文与公开表达采集 Agent", SourceTag.jsonForStep("step5_posts"));
        collectTaskMapper.insertPhaseStep(
                taskId, "step7_report", PHASE_REPORT, 610, "6.1",
                "公开资料核查报告 Agent", SourceTag.jsonForStep("step7_report"));
    }

    private String seedAgentTitle(String platform) {
        String plat = platform == null || platform.trim().isEmpty()
                ? "twitter" : platform.trim().toLowerCase();
        String label = platformLabel(plat);
        if ("twitter".equals(plat) || "weibo".equals(plat)
                || "youtube".equals(plat) || "bilibili".equals(plat)) {
            return label + " MCP Agent 采集";
        }
        return "Apify Agent · " + label + " 采集";
    }

    private String platformLabel(String platform) {
        if ("twitter".equals(platform)) {
            return "Twitter";
        }
        if ("weibo".equals(platform)) {
            return "微博";
        }
        if ("youtube".equals(platform)) {
            return "YouTube";
        }
        if ("bilibili".equals(platform)) {
            return "B站";
        }
        if ("instagram".equals(platform)) {
            return "Instagram";
        }
        if ("tiktok".equals(platform)) {
            return "TikTok";
        }
        if ("telegram".equals(platform)) {
            return "Telegram";
        }
        if ("facebook".equals(platform)) {
            return "Facebook";
        }
        if ("github".equals(platform)) {
            return "GitHub";
        }
        if ("linkedin".equals(platform)) {
            return "LinkedIn";
        }
        return platform;
    }

    private static String stringVal(Object v) {
        return v == null ? "" : String.valueOf(v).trim();
    }
}
