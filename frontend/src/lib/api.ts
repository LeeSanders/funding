export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000/api/v1";

export type ApiModule = {
  title: string;
  endpoint: string;
  description: string;
};

export const apiModules: ApiModule[] = [
  {
    title: "基金分析",
    endpoint: "/analysis/{code}",
    description: "按 6 位基金代码返回技术面、消息面、风险与建议。",
  },
  {
    title: "推荐列表",
    endpoint: "/recommendations?strategy=balanced",
    description: "按平衡 / 稳健 / 进取策略返回推荐池。",
  },
  {
    title: "持仓估值",
    endpoint: "/portfolio",
    description: "返回组合总收益、持仓收益和估值更新时间。",
  },
  {
    title: "OCR 识别",
    endpoint: "/ocr/simulate",
    description: "后续替换为真实图片上传和 OCR 解析链路。",
  },
];
