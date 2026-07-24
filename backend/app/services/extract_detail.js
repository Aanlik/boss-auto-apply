(function(){
    // 1. 提取原始文本
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
    if (start < 0) return JSON.stringify({jd: '', jd_tags: []});

    var jd = raw.substring(start);
    var NL = String.fromCharCode(10);

    // === 第一遍：行扫描 — 在 recruiter 处截断 ===
    var lines = jd.split(NL);
    var cutIdx = lines.length;
    for (var i = 0; i < lines.length - 1; i++) {
        var line = lines[i].trim();
        var next = lines[i + 1].trim();
        if (line.length >= 2 && line.length <= 4 &&
            (line.indexOf('女士') >= 0 || line.indexOf('先生') >= 0) &&
            (next.indexOf('活跃') >= 0 || next.indexOf('来过') >= 0)) {
            cutIdx = i; break;
        }
        if (line.length < 30 && (
            (line.indexOf('小时') >= 0 && line.indexOf('活跃') >= 0) ||
            (line.indexOf('天前') >= 0 && (line.indexOf('活跃') >= 0 || line.indexOf('来过') >= 0)) ||
            line === '刚刚活跃' || line === '今日活跃'
        )) { cutIdx = i; break; }
    }
    if (cutIdx < lines.length) lines = lines.slice(0, cutIdx);
    jd = lines.join(NL);

    // === 第二遍：噪音关键词截断 ===
    var noise = [
        '竞争力分析','刚刚活跃','今日活跃','BOSS 安全提示','BOSS直聘严禁',
        '公司介绍','工商信息','工作地址','更多职位','看过该职位',
        '精选职位','微信扫码分享','下载App','感兴趣 立即沟通','完善在线简历',
    ];
    for (var i = 0; i < noise.length; i++) {
        var pos = jd.indexOf(noise[i]);
        if (pos > 10 && pos < jd.length) jd = jd.substring(0, pos);
    }

    // === 第三遍：排版优化 ===
    lines = jd.split(NL);
    var clean = [];

    for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();

        // 跳过首部噪音短行（如 "举报"）
        if (clean.length === 0 && line.length < 10 &&
            line !== '职位描述' && line !== '岗位职责' && line !== '任职要求') continue;

        if (line === '') continue;  // 跳过空行，手动控制间距

        // 章节标题（如【岗位职责】、【任职要求】）前加空行
        if (/^[【\[].+[】\]]$/.test(line) && line.length < 20) {
            if (clean.length > 0) clean.push('');
            clean.push(line);
            continue;
        }

        // 编号列表项：确保独立成行，前加空行（节内第一项除外）
        var isListItem = /^[（(]?\d+[）).、]/.test(line);
        if (isListItem) {
            var prev = clean.length > 0 ? clean[clean.length - 1] : '';
            // 如果前一行不是空行也不是编号项也不是章节标题，加空行
            if (prev !== '' && !/^[（(]?\d+[）).、]/.test(prev) && !/^[【\[].+[】\]]$/.test(prev)) {
                clean.push('');
            }
            clean.push(line);
            continue;
        }

        // 普通行
        clean.push(line);
    }

    // 去尾部空行
    while (clean.length > 0 && clean[clean.length - 1] === '') clean.pop();

    // 去尾部孤立姓名
    while (clean.length > 0) {
        var last = clean[clean.length - 1];
        if (last.length >= 2 && last.length <= 4 &&
            (last.indexOf('女士') >= 0 || last.indexOf('先生') >= 0)) {
            clean.pop();
        } else break;
    }

    jd = clean.join(NL);

    // 标签
    var jobTags = [];
    var tagEls = document.querySelectorAll('.job-tags .tag-all span, .job-keyword-list span');
    for (var i = 0; i < tagEls.length; i++) {
        var t = tagEls[i].innerText.trim();
        if (t && t.length < 30 && t !== '职位描述') jobTags.push(t);
    }

    return JSON.stringify({jd: jd, jd_tags: jobTags, url: location.href});
})()
