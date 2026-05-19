-- ==================== verify tools ====================
local passed = 0
local failed = 0

-- desc: 测试什么功能， condition: 为真则通过， 失败时用 hint 补充说明
local verify = function (desc, condition, hintOnFail)
    if condition then
        passed = passed + 1
        print("  [PASS] " .. desc)
    else
        failed = failed + 1
        print("  [FAIL] " .. desc .. (hintOnFail and (" — " .. hintOnFail) or ""))
    end
end

local verify_summary = function()
    print("\n========== 测试结果 ==========")
    print("通过: " .. passed)
    print("失败: " .. failed)
    print("总计: " .. (passed + failed))

    if failed == 0 then
        print("✓ 全部通过！")
    else
        print("✗ 有失败的测试")
    end
    print("==============================")
end
print("开始跑测试用例:")
-- ==================== verify tools ====================

-- testcase: 1, 等级限制测试
local isFeatureOpen = function (lv)
    return lv >= 50 
end
verify("基础开关-到达等级", isFeatureOpen(50) == true, "到达等级未开启")
verify("基础开关-未到达等级", isFeatureOpen(49) == false, "未到达等级，却未开启")


-- 总结
verify_summary()
