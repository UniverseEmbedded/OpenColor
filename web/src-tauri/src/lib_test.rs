// Rust 后端单元测试
// 使用标准 Rust 测试框架

#[cfg(test)]
mod tests {
    use super::*;

    // 测试文件 MIME 类型猜测
    #[test]
    fn test_guess_mime() {
        use std::path::Path;
        
        assert_eq!(guess_mime(Path::new("test.png")), "image/png");
        assert_eq!(guess_mime(Path::new("test.jpg")), "image/jpeg");
        assert_eq!(guess_mime(Path::new("test.jpeg")), "image/jpeg");
        assert_eq!(guess_mime(Path::new("test.webp")), "image/webp");
        assert_eq!(guess_mime(Path::new("test.svg")), "image/svg+xml");
        assert_eq!(guess_mime(Path::new("test.unknown")), "application/octet-stream");
    }

    // 测试 oc 文件名解析
    #[test]
    fn test_parse_oc_short() {
        // 测试标准格式
        let result = parse_oc_short("oc1_mg_4c_RGBW.json");
        assert!(result.is_some());
        let short = result.unwrap();
        assert_eq!(short.get("scheme").unwrap().as_str().unwrap(), "oc1");
        assert_eq!(short.get("kind").unwrap().as_str().unwrap(), "mg");
        assert_eq!(short.get("variant").unwrap().as_str().unwrap(), "4c");
        assert_eq!(short.get("cs").unwrap().as_str().unwrap(), "RGBW");

        // 测试带喷嘴宽度的文件名
        let result = parse_oc_short("oc1_fl_std_noz040.json");
        assert!(result.is_some());
        let short = result.unwrap();
        assert_eq!(short.get("kind").unwrap().as_str().unwrap(), "fl");
        assert_eq!(short.get("nozzle_width_mm").unwrap().as_f64().unwrap(), 0.4);

        // 测试无效格式
        assert!(parse_oc_short("invalid.json").is_none());
        assert!(parse_oc_short("").is_none());
    }

    // 测试 display_key 生成
    #[test]
    fn test_display_from_short() {
        let short = serde_json::json!({
            "kind": "mg",
            "variant": "4c",
            "cs": "RGBW"
        });
        
        let result = display_from_short(&short);
        assert!(result.is_some());
        let (key, args) = result.unwrap();
        assert_eq!(key, "album.file.material_group");
        assert_eq!(args.get("cs").unwrap().as_str().unwrap(), "RGBW");
    }

    // 测试资源库 schema 版本
    #[test]
    fn test_default_library_schema_version() {
        assert_eq!(default_library_schema_version(), 2);
    }
}

// 引入被测试的函数
use crate::{guess_mime, parse_oc_short, display_from_short, default_library_schema_version};
