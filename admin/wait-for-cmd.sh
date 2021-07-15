#!/usr/bin/env bash
# Use this script to test if a given command produces an expected output.
#
# Based on
# Source https://github.com/vishnubob/wait-for-it/blob/master/wait-for-it.sh
#
WAITFORIT_cmdname=${0##*/}

echoerr() { if [[ $WAITFORIT_QUIET -ne 1 ]]; then echo "$@" 1>&2; fi }

usage()
{
    exit_code=$1
    cat << USAGE >&2
Usage:
    $WAITFORIT_cmdname [-g VALUE] [-s] [-t timeout] [-- command args]
    -g VALUE | --grep=VALUE     Grep the command output.
    -q | --quiet                Don't output any status messages
    -h | --help                 This help message
    -t TIMEOUT | --timeout=TIMEOUT
                                Timeout in seconds, zero for no timeout
    -- COMMAND ARGS             Execute command with args until exit code is 0
USAGE
    exit $exit_code
}

wait_for()
{
    if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
        echoerr "$WAITFORIT_cmdname: waiting $WAITFORIT_TIMEOUT seconds for '$WAITFORIT_CLI' to produce '$WAITFORIT_VALUE'"
    else
        echoerr "$WAITFORIT_cmdname: waiting for '$WAITFORIT_CLI' to produce '$WAITFORIT_VALUE' without a timeout"
    fi
    WAITFORIT_start_ts=$(date +%s)
    while :
    do
        if [[ "$WAITFORIT_VALUE" == "" ]]; then
            $WAITFORIT_CLI
        else
            $WAITFORIT_CLI | grep $WAITFORIT_VALUE
        fi
        WAITFORIT_result=$?

        if [[ $WAITFORIT_result -eq 0 ]]; then
            WAITFORIT_end_ts=$(date +%s)
            echoerr "$WAITFORIT_cmdname: $WAITFORIT_CLI is present after $((WAITFORIT_end_ts - WAITFORIT_start_ts)) seconds"
            break
        fi
        sleep 1
    done
    return $WAITFORIT_result
}

wait_for_wrapper()
{
    # In order to support SIGINT during timeout: http://unix.stackexchange.com/a/57692
    if [[ $WAITFORIT_QUIET -eq 1 ]]; then
        timeout $WAITFORIT_TIMEOUT $0 --child --quiet --grep=$WAITFORIT_VALUE --timeout=$WAITFORIT_TIMEOUT -- "$WAITFORIT_CLI" &
    else
        timeout $WAITFORIT_TIMEOUT $0 --child --grep=$WAITFORIT_VALUE --timeout=$WAITFORIT_TIMEOUT -- "$WAITFORIT_CLI" &
    fi
    WAITFORIT_PID=$!
    trap "kill -INT -$WAITFORIT_PID" INT
    wait $WAITFORIT_PID
    WAITFORIT_RESULT=$?
    if [[ $WAITFORIT_RESULT -ne 0 ]]; then
        echoerr "$WAITFORIT_cmdname: timeout occurred after waiting $WAITFORIT_TIMEOUT seconds for $WAITFORIT_CLI"
    fi
    return $WAITFORIT_RESULT
}

# process arguments
while [[ $# -gt 0 ]]
do
    case "$1" in
        --child)
        WAITFORIT_CHILD=1
        shift 1
        ;;
        -g)
        WAITFORIT_VALUE="$2"
        if [[ $WAITFORIT_VALUE == "" ]]; then break; fi
        shift 2
        ;;
        --grep=*)
        WAITFORIT_VALUE="${1#*=}"
        shift 1
        ;;
        -h)
        usage
        ;;
        -t)
        WAITFORIT_TIMEOUT="$2"
        if [[ $WAITFORIT_TIMEOUT == "" ]]; then break; fi
        shift 2
        ;;
        --timeout=*)
        WAITFORIT_TIMEOUT="${1#*=}"
        shift 1
        ;;
        --)
        shift
        WAITFORIT_CLI="$@"
        break
        ;;
        --help)
        usage
        ;;
        *)
        echoerr "Unknown argument: $1"
        usage 1
        ;;
    esac
done

if [[ "$WAITFORIT_CLI" == "" ]]; then
    echoerr "Error: you need to provide a command to test."
    usage 1
fi

WAITFORIT_TIMEOUT=${WAITFORIT_TIMEOUT:-15}
WAITFORIT_QUIET=${WAITFORIT_QUIET:-0}
WAITFORIT_CHILD=${WAITFORIT_CHILD:-0}

if [[ $WAITFORIT_CHILD -gt 0 ]]; then
    wait_for
    WAITFORIT_RESULT=$?
    exit $WAITFORIT_RESULT
else
    if [[ $WAITFORIT_TIMEOUT -gt 0 ]]; then
        wait_for_wrapper
        WAITFORIT_RESULT=$?
    else
        wait_for
        WAITFORIT_RESULT=$?
    fi
fi

exit $WAITFORIT_RESULT
