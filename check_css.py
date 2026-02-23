import glob, os

css_files = glob.glob("/opt/clawfans/frontend/.next/static/chunks/*.css")
print(f"CSS files: {css_files}")
for f in css_files:
    size = os.path.getsize(f)
    with open(f) as fp:
        content = fp.read()
    grid_count = content.count("grid-template-columns")
    flex_count = content.count("display:flex")
    print(f"\nFile: {os.path.basename(f)}")
    print(f"  Size: {size} bytes")
    print(f"  grid-template-columns occurrences: {grid_count}")
    print(f"  display:flex occurrences: {flex_count}")
    # Show a sample
    idx = content.find("grid-template-columns")
    if idx >= 0:
        print(f"  Sample: {content[max(0,idx-20):idx+60]!r}")
