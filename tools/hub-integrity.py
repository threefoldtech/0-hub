import redis
import sys

r = redis.Redis("10.241.0.232", 9901)
info = redis.client.parse_info(r.execute_command("NSINFO minio"))

entries = info['entries']
print("Keys: %d" % entries)
print("Starting integrity checking...")

checked = 0
nextkey = ""
errors = []

response = r.execute_command("SCANX")

while True:
    for key in response[1]:
        if r.execute_command("CHECK", key[0]) == 0:
            errors.append(key[0])

    checked += len(response[1])

    sys.stdout.write("\rIntegrity check: %.02f %% [%d/%d, %d errors]" % (((checked / entries) * 100), checked, entries, len(errors)))

    if response[0] is None:
        break

    response = r.execute_command("SCANX", response[0])

print("")
print("Integrity check done, errors: %d" % len(errors))
print(errors)
