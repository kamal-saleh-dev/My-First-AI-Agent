# unreal_templates.py — Unreal Engine C++ validation, fixes, and prompts
# Edit here without touching agent.py
import re

def validate_unreal(code):
    required = ["#include", "GENERATED_BODY"]
    for r in required:
        if r.lower() not in code.lower():
            return False, f"Missing Unreal requirement: {r}"

    if ".generated.h" not in code:
        return False, "Missing .generated.h include"

    # regex صح عشان مينفعش يعتبر UActorComponent كـ UComponent أو UObject
    if re.search(r'public\s+UComponent\b', code):
        return False, "Invalid Unreal inheritance: Use UActorComponent instead of UComponent"

    if re.search(r'public\s+UObject\b', code):
        return False, "Component must inherit from UActorComponent, not UObject"

    return True, "Valid Unreal Header"

def auto_fix_unreal_header(header_code):
    """
    Inject missing .generated.h include if absent.
    """
    if ".generated.h" in header_code:
        return header_code, False

    # Extract class name
    class_match = re.search(
        r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)",
        header_code
    )

    if not class_match:
        return header_code, False

    class_name = class_match.group(1)

    include_line = f'#include "{class_name}.generated.h"\n'

    # نحاول نحطه بعد آخر include
    includes = list(re.finditer(r'#include\s+["<].*[">]', header_code))
    if includes:
        last_include = includes[-1]
        insert_pos = last_include.end()
        fixed_header = (
            header_code[:insert_pos]
            + "\n"
            + include_line
            + header_code[insert_pos:]
        )
    else:
        # لو مفيش includes خالص
        fixed_header = include_line + header_code

    return fixed_header, True

UNREAL_SYSTEM_PROMPT = """You are a senior Unreal Engine C++ developer.

STRICT OUTPUT RULES:
1) Return EXACTLY TWO ```cpp blocks. Nothing else outside them.
2) First block = Header (.h), Second block = CPP (.cpp)
3) Header MUST:
   - Start with #pragma once
   - #include "CoreMinimal.h"
   - #include "Components/ActorComponent.h"
   - #include "<ExactClassName>.generated.h"
   - UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
   - class MYGAME_API <ClassName> : public UActorComponent
   - GENERATED_BODY()
   - Declare constructor, ALL functions, UPROPERTY, UFUNCTION, delegates
4) CPP MUST:
   - #include "<ExactClassName>.h" (SAME name as the class file)
   - Implement constructor and ALL declared functions
5) NO text or explanations outside the two code blocks.

EXAMPLE:
```cpp
#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "MyComp.generated.h"

UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
class MYGAME_API UMyComp : public UActorComponent
{
    GENERATED_BODY()
public:
    UMyComp();
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Stats")
    float Value;
    UFUNCTION(BlueprintCallable)
    void DoSomething(float Amount);
protected:
    virtual void BeginPlay() override;
};
```
```cpp
#include "MyComp.h"

UMyComp::UMyComp()
{
    PrimaryComponentTick.bCanEverTick = false;
}
void UMyComp::BeginPlay()
{
    Super::BeginPlay();
}
void UMyComp::DoSomething(float Amount)
{
    Value -= Amount;
}
```"""


def save_unreal_scripts(matches: list, folder_name: str) -> bool:
    """
    Validate and save Unreal .h + .cpp files.
    Called from extract_and_save_scripts when domain == 'unreal'.
    """
    import os, re

    if len(matches) < 2:
        print("❌ Unreal requires header and cpp blocks.")
        return False

    header_code = matches[0].strip()
    cpp_code    = matches[1].strip()

    # Validate + auto-fix header
    is_valid, msg = validate_unreal(header_code)
    if not is_valid and "generated.h" in msg:
        print("⚠ Missing .generated.h — attempting auto-fix...")
        header_code, fixed = auto_fix_unreal_header(header_code)
        if fixed:
            is_valid, msg = validate_unreal(header_code)

    if not is_valid:
        print(f"❌ Validation Failed: {msg}")
        return False

    if "::" not in cpp_code:
        print("❌ Unreal CPP missing implementation (:: not found)")
        return False

    # Structural validation
    cpp_class_names = set(re.findall(r'([A-Za-z_][A-Za-z0-9_]*)::'  , cpp_code))
    known_overrides = {"BeginPlay","TickComponent","EndPlay","InitializeComponent",
                       "GetLifetimeReplicatedProps","SetupInputComponent","PostInitializeComponents"}
    header_clean    = re.sub(r'\b(UFUNCTION|UPROPERTY|UCLASS|USTRUCT|UENUM)\s*\([^)]*\)', '', header_code)
    declared_funcs  = set(re.findall(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^)]*\)\s*(?:const\s*)?;', header_clean))
    implemented     = re.findall(r'::([A-Za-z_][A-Za-z0-9_]*)\s*\(', cpp_code)

    for func in implemented:
        if func in cpp_class_names or func.lstrip('~') in cpp_class_names: continue
        if func in known_overrides: continue
        if func not in declared_funcs:
            print(f"⚠ Note: '{func}' not in header — treating as override.")

    # Extract class name and save
    m = re.search(r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)", header_code)
    class_name  = m.group(1) if m else "UnrealClass"
    header_path = os.path.join(folder_name, f"{class_name}.h")
    cpp_path    = os.path.join(folder_name, f"{class_name}.cpp")

    with open(header_path, "w", encoding="utf-8") as f: f.write(header_code)
    with open(cpp_path,    "w", encoding="utf-8") as f: f.write(cpp_code)

    print(f"\n💾 Saved -> {header_path}")
    print(f"💾 Saved -> {cpp_path}")
    return True
