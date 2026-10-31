(function () {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();

  var baseText = { color: ink, fontFamily: 'Instrument Sans, PingFang SC, sans-serif' };
  var axisLabel = { color: muted, fontSize: 11 };

  // ---------- 图 1：品类 SKU 占比 vs 销量权重 ----------
  var chartCat = echarts.init(document.getElementById('chart-cat'), null, { renderer: 'svg' });
  chartCat.setOption({
    animation: false,
    color: [accent, accent2],
    grid: { left: 74, right: 54, top: 44, bottom: 30, containLabel: false },
    legend: {
      top: 6, left: 74, itemWidth: 10, itemHeight: 10, itemGap: 18,
      textStyle: { color: muted, fontSize: 11 }
    },
    tooltip: {
      trigger: 'axis', appendToBody: true, axisPointer: { type: 'shadow' },
      backgroundColor: bg2, borderColor: rule, textStyle: { color: ink, fontSize: 12 },
      formatter: function (p) {
        var out = '<b>' + p[0].name + '</b>';
        p.forEach(function (d) { out += '<br/>' + d.seriesName + '：' + d.value + '%'; });
        return out;
      }
    },
    xAxis: {
      type: 'value', max: 40, splitNumber: 4,
      axisLabel: { formatter: '{value}%', color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category', inverse: true,
      data: ['内裤', '内衣', '打底/保暖', '袜子', '家居服', '胸贴'],
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: ink } },
      axisTick: { show: false }
    },
    series: [
      {
        name: 'SKU 占比', type: 'bar', barWidth: 11, barGap: '14%',
        data: [33.4, 30.6, 17.2, 12.9, 3.1, 2.6],
        itemStyle: { color: accent },
        label: { show: true, position: 'right', color: accent, fontSize: 11, formatter: '{c}%' }
      },
      {
        name: '销量权重', type: 'bar', barWidth: 11,
        data: [34.5, 33.6, 8.8, 14.7, 0.2, 8.3],
        itemStyle: { color: accent2 },
        label: { show: true, position: 'right', color: accent2, fontSize: 11, formatter: '{c}%' }
      }
    ]
  });
  window.addEventListener('resize', function () { chartCat.resize(); });

  // ---------- 图 2：价格带分布（堆叠） ----------
  var bands = ['<30', '30-39', '40-49', '50-69', '70-99', '100+'];
  var bandColors = [muted + '66', accent2 + '55', accent2 + 'A6', accent + '80', accent + 'CC', accent];
  var bandData = {
    '内裤': [3, 19, 35, 129, 15, 1],
    '内衣': [1, 0, 1, 29, 137, 17],
    '打底/保暖': [7, 5, 3, 28, 45, 16],
    '袜子': [19, 34, 19, 3, 3, 0],
    '家居服': [0, 0, 0, 1, 0, 18],
    '胸贴': [3, 1, 1, 11, 0, 0]
  };
  var catNames = ['内裤', '内衣', '打底/保暖', '袜子', '家居服', '胸贴'];

  var chartPrice = echarts.init(document.getElementById('chart-price'), null, { renderer: 'svg' });
  chartPrice.setOption({
    animation: false,
    grid: { left: 74, right: 30, top: 52, bottom: 32, containLabel: false },
    legend: {
      top: 8, left: 74, itemWidth: 9, itemHeight: 9, itemGap: 12,
      textStyle: { color: muted, fontSize: 11 }, data: bands
    },
    tooltip: {
      trigger: 'axis', appendToBody: true, axisPointer: { type: 'shadow' },
      backgroundColor: bg2, borderColor: rule, textStyle: { color: ink, fontSize: 12 },
      formatter: function (p) {
        var total = 0, out = '<b>' + p[0].name + '</b>';
        p.forEach(function (d) { total += d.value; });
        p.forEach(function (d) {
          if (d.value > 0) {
            out += '<br/>¥' + d.seriesName + '：' + d.value + ' 个（' + Math.round(d.value / total * 100) + '%）';
          }
        });
        return out;
      }
    },
    xAxis: {
      type: 'value',
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category', inverse: true, data: catNames,
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: ink } },
      axisTick: { show: false }
    },
    series: bands.map(function (b, i) {
      return {
        name: b, type: 'bar', stack: 'price', barWidth: 16,
        itemStyle: { color: bandColors[i] },
        label: {
          show: true, position: 'inside', color: bg2, fontSize: 10, fontWeight: 600,
          formatter: function (p) { return p.value >= 18 ? p.value : ''; }
        },
        data: catNames.map(function (c) { return bandData[c][i]; })
      };
    })
  });
  window.addEventListener('resize', function () { chartPrice.resize(); });

  // ---------- 图 3：袜子款式分布 ----------
  var sockNames = ['中筒袜', '堆堆袜', '船袜/短袜', '护膝/过膝', '小腿/长筒', '其他'];
  var sockVals = [26, 25, 14, 8, 3, 2];
  var chartSocks = echarts.init(document.getElementById('chart-socks'), null, { renderer: 'svg' });
  chartSocks.setOption({
    animation: false,
    grid: { left: 76, right: 46, top: 16, bottom: 26, containLabel: false },
    tooltip: {
      trigger: 'axis', appendToBody: true, axisPointer: { type: 'shadow' },
      backgroundColor: bg2, borderColor: rule, textStyle: { color: ink, fontSize: 12 },
      formatter: function (p) {
        var d = p[0];
        return '<b>' + d.name + '</b><br/>' + d.value + ' 个 SKU（占袜子 ' + Math.round(d.value / 78 * 100) + '%）';
      }
    },
    xAxis: {
      type: 'value', max: 30, splitNumber: 3,
      axisLabel: { color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category', inverse: true, data: sockNames,
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: ink } },
      axisTick: { show: false }
    },
    series: [{
      type: 'bar', barWidth: 15,
      data: sockVals.map(function (v, i) {
        return { value: v, itemStyle: { color: i < 2 ? accent : accent2 } };
      }),
      label: {
        show: true, position: 'right', color: ink, fontSize: 11, fontWeight: 600,
        formatter: function (p) { return p.value + ' 个'; }
      }
    }]
  });
  window.addEventListener('resize', function () { chartSocks.resize(); });

  // ---------- 图 4：标题卖点词覆盖率 ----------
  var wordNames = ['无痕', '纯棉', '抗菌', '聚拢', '新款', '小胸', '10A 抗菌', '明星同款', '加长裆'];
  var wordVals = [37.7, 37.6, 34.4, 29.1, 27.2, 28.3, 17.1, 20.0, 7.9];
  var sortedWord = wordNames.map(function (n, i) { return { n: n, v: wordVals[i] }; })
    .sort(function (a, b) { return a.v - b.v; });

  var chartWords = echarts.init(document.getElementById('chart-words'), null, { renderer: 'svg' });
  chartWords.setOption({
    animation: false,
    grid: { left: 90, right: 54, top: 12, bottom: 28, containLabel: false },
    tooltip: {
      trigger: 'axis', appendToBody: true, axisPointer: { type: 'shadow' },
      backgroundColor: bg2, borderColor: rule, textStyle: { color: ink, fontSize: 12 },
      formatter: function (p) {
        var d = p[0];
        return '<b>' + d.name + '</b><br/>覆盖 ' + d.value + '% 的商品标题（约 ' + Math.round(d.value * 6.04) + ' 条）';
      }
    },
    xAxis: {
      type: 'value', max: 40, splitNumber: 4,
      axisLabel: { formatter: '{value}%', color: muted, fontSize: 11 },
      axisLine: { lineStyle: { color: rule } },
      splitLine: { lineStyle: { color: rule, type: 'dashed' } }
    },
    yAxis: {
      type: 'category', data: sortedWord.map(function (d) { return d.n; }),
      axisLabel: { color: ink, fontSize: 12 },
      axisLine: { lineStyle: { color: ink } },
      axisTick: { show: false }
    },
    series: [{
      type: 'bar', barWidth: 13,
      data: sortedWord.map(function (d) {
        return { value: d.v, itemStyle: { color: d.v >= 25 ? accent : accent2 } };
      }),
      label: {
        show: true, position: 'right', color: ink, fontSize: 11, fontWeight: 600,
        formatter: '{c}%'
      }
    }]
  });
  window.addEventListener('resize', function () { chartWords.resize(); });
})();
