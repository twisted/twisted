%%
%% Test for amp client module.
%%

-module(test_amp).

-export([]).

-include_lib("eunit/include/eunit.hrl").


parse_int_prefixed_error_empty_test() ->
    ?_assertMatch(error, amp:parse_int_prefixed(<<>>)).


parse_int_prefixed_error_no_null_test() ->
    ?_assertMatch(error, amp:parse_int_prefixed(<<0, 1, 1>>)).


parse_int_prefixed_error_no_data_test() ->
    ?_assertMatch(error, amp:parse_int_prefixed(<<1, 0, 0>>)).

parse_int_prefixed_error_wrong_length_test() ->
    ?_assertMatch(error, amp:parse_int_prefixed(<<0, 2, 1, 0, 0>>)).


parse_int_prefixed_error_after_one_token_test() ->
    ?_assertMatch(error, amp:parse_int_prefixed(<<0, 2, 5, 4, 0, 1, 0, 0>>)).


parse_int_prefixed_empty_test() ->
    ?_assertMatch([], amp:parse_int_prefixed(<<0, 0>>)).

parse_int_prefixed_basic_test() ->
    ?_assertMatch([[1]], amp:parse_int_prefixed(<<0, 1, 1, 0, 0>>)).

parse_int_prefixed_two_tokens_test() ->
    ?_assertMatch([[1], [4, 5]], amp:parse_int_prefixed(<<0, 1, 1, 0, 2, 4, 5, 0, 0>>)).


build_int_prefixed_empty_test() ->
    ?_assertMatch(<<0, 0>>, amp:build_int_prefixed([])).

build_int_prefixed_basic_test() ->
    ?_assertMatch(<<0, 1, 49, 0, 0>>, amp:build_int_prefixed(["1"])).

build_int_prefixed_two_tokens_test() ->
    ?_assertMatch(<<0, 2, 51, 52, 0, 1, 53, 0, 0>>, amp:build_int_prefixed(["34", "5"])).

build_int_prefixed_int_test() ->
    ?_assertMatch(<<0, 3, 49, 50, 51, 0, 0>>, amp:build_int_prefixed([123])).

% TODO: define another float serialization
% build_int_prefixed_float_test() -> [
%    ?_assertMatch(<<0, 4, 52, 46, 53, 54, 0, 0>>, amp:build_int_prefixed([4.56]))
%].

build_int_prefixed_boolean_test_() -> [
    ?_assertMatch(<<0, 4, 84, 114, 117, 101, 0, 0>>, amp:build_int_prefixed([true])),
    ?_assertMatch(<<0, 5, 70, 97, 108, 115, 101, 0, 0>>, amp:build_int_prefixed([false]))
].


parse_response_test() ->
    ?_assertMatch({value, "10", ["foo"]},
        amp:parse_response(amp:build_int_prefixed(["_answer", "10", "foo"]))).

parse_response_error_test() ->
    ?_assertMatch({error, "11", ["bar"]},
        amp:parse_response(amp:build_int_prefixed(["_error", "11", "bar"]))).

parse_response_wrong_data_test() ->
    ?_assertMatch({error, ["foo", "11", "bar"]},
        amp:parse_response(amp:build_int_prefixed(["foo", "11", "bar"]))).


make_command_test() ->
    ?_assertMatch(["_ask", "124", "_command", "foo", "bar", "baz"],
        amp:parse_int_prefixed(amp:make_command(["foo", "bar", "baz"], "124"))).

