from datallog import automation

"""
To run this automation, you need run `datallog run {{automation_name}}

To push the automation to the Datallog service, use `datallog push`.

"""


@automation()
def main(seed):
    return "Hello, World!"
