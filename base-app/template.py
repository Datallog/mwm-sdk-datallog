from datallog import core_step, step

"""
To run this application, you need run `datallog run {{app_name}}

To push the applications to the Datallog service, use `datallog push`.

"""


@core_step(next_step="second_step")
def first_step(seed):
    return "Hello, World!"


@step()
def second_step(seed):
    return seed.upper()
