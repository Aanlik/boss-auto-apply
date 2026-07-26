(function(){
    // ── 1. 提取职位描述主体文本 ──
    var sections = document.querySelectorAll('.job-detail-section');
    var raw = '';
    for (var i = 0; i < sections.length; i++) {
        var t = sections[i].innerText || '';
        if (t.indexOf('职位描述') >= 0 && t.length > raw.length) raw = t;
    }
    if (!raw) raw = document.body ? document.body.innerText : '';

    var start = raw.indexOf('职位描述');
    if (start < 0) start = raw.indexOf('岗位职责');
    if (start < 0) start = raw.indexOf('任职要求');
    if (start < 0) start = raw.indexOf('工作内容');
    if (start < 0) return JSON.stringify({jd: '', jd_tags: []});

    var jd = raw.substring(start);
    var sectionStarts = ['岗位职责', '工作职责', '职位职责', '职责描述', '工作内容', '职责', '任职要求', '岗位要求', '职位要求', '要求'];
    var substantiveStart = -1;
    for (var si = 0; si < sectionStarts.length; si++) {
        var sp = jd.indexOf(sectionStarts[si]);
        if (sp > 0 && (substantiveStart < 0 || sp < substantiveStart)) substantiveStart = sp;
    }
    // BOSS 详情页顶部经常混入行业标签、规模包装和公司营销文案；
    // 如果后面出现正式职责/要求段，直接从正式段开始。
    if (substantiveStart > 0) jd = jd.substring(substantiveStart);
    var NL = String.fromCharCode(10);

    // ── 2. 噪声关键词硬截断（在 recruiter 信息出现前截断） ──
    var noiseTerms = [
        '竞争力分析', 'BOSS 安全提示', 'BOSS直聘严禁', 'BOSS直聘安全提示',
        '公司介绍', '工商信息', '工作地址', '更多职位', '看过该职位',
        '精选职位', '微信扫码分享', '下载App', '下载 APP', '打开App',
        '感兴趣 立即沟通', '完善在线简历', '看了此职位的人', '热门职位',
        '猜你喜欢', '为你推荐', '相似职位', '你可能还喜欢',
        '登录 查看', '扫码下载', '微信扫码',
        '职位亮点', '职位诱惑', '职位福利', '公司福利', '福利待遇',
        '我们是谁', '我们能给你什么', '我们需要：', '我们需要:', '加入我们',
    ];
    for (var i = 0; i < noiseTerms.length; i++) {
        var pos = jd.indexOf(noiseTerms[i]);
        if (pos > 10 && pos < jd.length) {
            jd = jd.substring(0, pos);
        }
    }

    // ── 3. 行扫描 ──
    var lines = jd.split(NL);
    var clean = [];

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (line === '') continue;
        if (line === '在线') continue;

        // 跳过首部噪音短行
        if (clean.length === 0 && line.length < 10 &&
            !/^(职位描述|岗位职责|任职要求|工作内容|工作职责|职位职责|职责|岗位要求|职位要求|要求)[:：]?$/.test(line)) continue;

        // ── 识别并跳过 recruiter 行 ──
        // 模式: "X女士" "X先生" 的短行
        if (line.length >= 2 && line.length <= 6 &&
            (line.indexOf('女士') >= 0 || line.indexOf('先生') >= 0)) continue;

        // 模式: "姓名 + 在线" 的行（如 "冯女士在线"）
        if (line.indexOf('在线') >= 0 && line.length < 30 &&
            (line.indexOf('女士') >= 0 || line.indexOf('先生') >= 0)) continue;

        // 模式: "X天前活跃" "刚刚活跃" "今日活跃" "X小时前活跃"
        if (line.length < 20 &&
            ((line.indexOf('活跃') >= 0 && (line.indexOf('天前') >= 0 || line.indexOf('小时') >= 0 || line === '刚刚活跃' || line === '今日活跃')) ||
             (line.indexOf('来过') >= 0 && line.indexOf('天前') >= 0))) continue;

        // 模式: 公司名 + 分隔符 + HR职位 (如 "示例生物科技 · 人事专员")
        if (line.indexOf('·') >= 0 && line.length < 80) {
            var parts = line.split('·');
            if (parts.length >= 2) {
                var lastPart = parts[parts.length - 1].trim();
                if (lastPart.length < 12 &&
                    (lastPart.indexOf('经理') >= 0 || lastPart.indexOf('专员') >= 0 ||
                     lastPart.indexOf('HR') >= 0 || lastPart.indexOf('主管') >= 0 ||
                     lastPart.indexOf('总监') >= 0 || lastPart.indexOf('招聘') >= 0)) continue;
            }
        }

        // 模式: 纯公司名行（短行且前面刚跳过 recruiter）
        // 当上一行是 recruiter 信息时，当前短公司名行也跳过
        if (line.length < 40 && clean.length > 0) {
            var prev = clean[clean.length - 1];
            if (prev.length < 20 &&
                ((prev.indexOf('活跃') >= 0) || (prev.indexOf('在线') >= 0) ||
                 (prev.indexOf('女士') >= 0) || (prev.indexOf('先生') >= 0))) {
                // 检查当前行是否像公司名
                if (line.indexOf('职位描述') < 0 && line.indexOf('岗位职责') < 0 && line.indexOf('任职') < 0) {
                    continue;
                }
            }
        }

        // 模式: 纯福利/标签短行（"HRBP经验" / "五险一金" / "带薪年假"）
        if (line.length < 15 && line.indexOf('经验') >= 0 &&
            line.indexOf('岗位') < 0 && line.indexOf('任职') < 0 && line.indexOf('职位') < 0 && line.indexOf('工作') < 0) {
            // 跳过孤立的 "X年经验" 标签行
            continue;
        }

        // 章节标题 — 前加空行
        if (/^[【\[].+[】\]]$/.test(line) && line.length < 20) {
            if (clean.length > 0) clean.push('');
            clean.push(line);
            continue;
        }

        // 编号列表项 — 独立成行
        var isListItem = /^[（(]?\d+[）).、]/.test(line);
        if (isListItem) {
            var prevLine = clean.length > 0 ? clean[clean.length - 1] : '';
            if (prevLine !== '' && !/^[（(]?\d+[）).、]/.test(prevLine) && !/^[【\[].+[】\]]$/.test(prevLine)) {
                clean.push('');
            }
            clean.push(line);
            continue;
        }

        clean.push(line);
    }

    // ── 4. 尾部清理 ──
    // 去掉尾部空行
    while (clean.length > 0 && clean[clean.length - 1] === '') clean.pop();

    // 去掉尾部孤立姓名 / recruiter 行
    while (clean.length > 0) {
        var last = clean[clean.length - 1];
        if (last.length >= 2 && last.length <= 6 &&
            (last.indexOf('女士') >= 0 || last.indexOf('先生') >= 0)) {
            clean.pop();
            // 继续尝试去掉前面的空行或公司名
            while (clean.length > 0 && clean[clean.length - 1] === '') clean.pop();
            // 尝试去掉前面的公司名短行
            if (clean.length > 0) {
                var before = clean[clean.length - 1];
                if (before.length < 30 && before.indexOf('职位') < 0 && before.indexOf('岗位') < 0) {
                    clean.pop();
                }
            }
        } else if (last.length < 30 && last.indexOf('·') >= 0) {
            // 尾部 "公司 · 职位" recruiter 行
            clean.pop();
            while (clean.length > 0 && clean[clean.length - 1] === '') clean.pop();
        } else break;
    }

    jd = clean.join(NL);

    // ── 5. 提取标签 ──
    var jobTags = [];
    var tagEls = document.querySelectorAll('.job-tags .tag-all span, .job-keyword-list span, .job-tag');
    for (var i = 0; i < tagEls.length; i++) {
        var t = (tagEls[i].innerText || '').trim();
        if (t && t.length < 30 && t !== '职位描述' && t !== '岗位职责') jobTags.push(t);
    }

    // ── 6. 提取企业工商注册名称 ──
    function cleanCompanyName(name) {
        return (name || '')
            .replace(/\s*[-–—]\s*Boss直聘.*$/i, '')
            .replace(/\s*-\s*看准网.*$/i, '')
            .replace(/^(公司全称|企业名称|工商注册名|注册名称|公司名称)[:：\s]*/, '')
            .trim();
    }

    function extractRegisteredNameFromText(text) {
        var source = (text || '').replace(/\s+/g, ' ').trim();
        var patterns = [
            /(公司全称|企业名称|工商注册名|注册名称|公司名称)[:：\s]+([^|｜\n\r]{2,80}?(?:公司|集团|中心|事务所|合伙企业|个体工商户))/,
            /(公司全称|企业名称|工商注册名|注册名称|公司名称)[:：\s]+([^|｜\n\r]{4,80})/,
        ];
        for (var p = 0; p < patterns.length; p++) {
            var match = source.match(patterns[p]);
            if (match && match[2]) return cleanCompanyName(match[2]);
        }
        return '';
    }

    var companyName = '';
    var businessEls = document.querySelectorAll('.business-info, .business-detail, .company-business, .company-info, .job-company-info, .sider-company, .level-list');
    for (var b = 0; b < businessEls.length; b++) {
        companyName = extractRegisteredNameFromText(businessEls[b].innerText || '');
        if (companyName) break;
    }
    if (!companyName) companyName = extractRegisteredNameFromText(document.body ? document.body.innerText : '');

    // 取不到注册名时，才回退到页面展示名
    if (!companyName) {
        var companyEl = document.querySelector('.company-name a, .company-name, .info-company .name, .job-company-info .name');
        if (companyEl) companyName = cleanCompanyName(companyEl.innerText || '');
    }
    if (!companyName || companyName.length < 2) {
        var altEl = document.querySelector('[ka="job-detail-company_name"]');
        if (altEl) companyName = cleanCompanyName(altEl.innerText || '');
    }
    if (!companyName || companyName.length < 2) {
        var titleParts = document.title.split('-');
        if (titleParts.length >= 2) companyName = cleanCompanyName(titleParts[titleParts.length - 1]);
    }

    return JSON.stringify({jd: jd, jd_tags: jobTags, company_name: companyName, url: location.href});
})()
