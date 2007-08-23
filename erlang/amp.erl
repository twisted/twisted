%%
%% AMP client.
%%

-module(amp).

-export([start_client/2, stop_client/1, client/2, sum/3, divide/3,
         parse_int_prefixed/1, build_int_prefixed/1, parse_response/1,
         make_command/2]).


%%
%% Start a new AMP client in a process.
%%
%% @param Host: the address of the AMP server.
%% @type Host: C{string}
%% @param Port: the port of the AMP server.
%% @type Port: C{integer}
%%
%% @return: the PID of the client process.
%% @rtype: C{pid}
%%
start_client(Host, Port) ->
    spawn(amp, client, [Host, Port]).


%%
%% Stop a previously started AMP client.
%%
%% @param AmpClientPid: the PID of the client process, returned by
%%     C{start_client}.
%% @type AmpClientPid: C{pid}
%%
stop_client(AmpClientPid) ->
    AmpClientPid ! stop.


%%
%% Create a new client connection, and start a new AMP client loop. Don't call
%% this, use start_client instead.
%%
%% @param Host: the address of the AMP server.
%% @type Host: C{string}
%% @param Port: the port of the AMP server.
%% @type Port: C{integer}
%%
client(Host, Port) ->
    case make_connect(Host, Port) of
        {ok, Socket} ->
            client_loop(Socket, 1);
        {error, Reason} ->
            io:format("Error in connection: ~p~n", [Reason]),
            exit({error, Reason})
    end.


%%
%% Main client loop for AMP.
%%
%% @param Socket: previously connected socket.
%% @type Socket: C{socket}
%% @param Counter: internal counter used to identify request.
%% @type Counter: C{integer}
%%
client_loop(Socket, Counter) ->
    receive
        {command, CallPid, ArgList} ->
            CounterAsList = integer_to_list(Counter),
            Cmd = make_command(ArgList, CounterAsList),
            case send_command(Socket, Cmd) of
                {value, CounterAsList, Data} ->
                    CallPid ! {value, Data};
                {error, CounterAsList, Data} ->
                    CallPid ! {error, Data};
                {error, Reason} ->
                    CallPid ! {error, Reason}
            end,
            client_loop(Socket, Counter + 1);
        stop ->
            gen_tcp:close(Socket)
    end.


%%
%% Create a connection to an AMP server.
%%
%% @param Host: the address of the AMP server.
%% @type Host: C{string}
%% @param Port: the port of the AMP server.
%% @type Port: C{integer}
%%
%% @return: a tuple of ok, connected socket.
%% @rtype: C{tuple}
%%
make_connect(Host, Port) ->
    gen_tcp:connect(Host, Port, [binary, {packet, 0}]).


%%
%% Send a AMP command over a socket connection, and parse the result.
%%
%% @param Socket: a connected socket.
%% @type Socket: C{socket}
%% @param Cmd: a command previously build with C{make_command}.
%% @type Cmd: C{binary}
%%
%% @return: data parsed from AMP result.
%% @rtype: C{tuple}
%%
send_command(Socket, Cmd) ->
    case gen_tcp:send(Socket, Cmd) of
        ok ->
            case wait_reply(Socket, 1000) of
                {value, Reply} ->
                    parse_response(Reply);
                timeout ->
                    timeout
            end;
        {error, Reason} ->
            {error, Reason}
    end.


%%
%% Parse a response to an AMP command.
%%
%% @param BinData: raw result for the AMP command.
%% @type BinData: C{binary}
%%
%% @return: parsed result of the command.
%% @rtype: C{tuple}
%%
parse_response(BinData) ->
    Data = parse_int_prefixed(BinData),
    case Data of
        ["_answer", AnswerID | Rest] ->
            {value, AnswerID, Rest};
        ["_error", AnswerID | Rest] ->
            {error, AnswerID, Rest};
        _ ->
            {error, Data}
    end.


%%
%% Build body of an AMP command.
%%
%% @param ArgList: name of the command, and its arguments.
%% @type ArgList: C{list}
%% @param Tag: AMP tag used to identify answer.
%% @type Tag: C{string}
%%
make_command(ArgList, Tag) ->
    build_int_prefixed(["_ask", Tag, "_command" | ArgList]).


%%
%% Parse binary data as int16-prefixed data NULL terminated.
%%
%% @param BinData: data to parse.
%% @type BinData: C{binary}
%%
%% @return: tokens read from binary data.
%% @rtype: C{list}
%%
parse_int_prefixed(BinData) ->
    parse_int_prefixed(BinData, []).


%%
%% Parse binary data as int16-prefixed data NULL terminated.
%%
%% @param BinData: data to parse.
%% @type BinData: C{binary}
%% @param List: used to hold temporary result during recursion.
%% @type List: C{list}
%%
%% @return: tokens read from binary data.
%% @rtype: C{list}
%%
parse_int_prefixed(BinData, List) ->
    case BinData of
        <<0, 0>> ->
            List;
        <<Prefix:16, RemainData/binary>> ->
            BinaryLength = length(binary_to_list(RemainData)),
            TooShort = if
                BinaryLength < Prefix ->
                    true;
                true ->
                    false
            end,
            case TooShort of
                true ->
                    error;
                false ->
                    {ReadData, Remain} = split_binary(RemainData, Prefix),
                    NewList = lists:append(List, [binary_to_list(ReadData)]),
                    parse_int_prefixed(Remain, NewList)
            end;
        _ ->
            error
    end.


%%
%% Build int16-prefixed binary data NULL terminated.
%%
%% @param ListData: tokens of the data.
%% @type ListData: C{list}
%%
%% @return: int16-prefixed raw data.
%% @rtype: C{binary}
%%
build_int_prefixed(ListData) ->
    BuiltData = build_int_prefixed(ListData, <<>>),
    % Add final NULL values
    <<BuiltData/binary, 0, 0>>.


%%
%% Inner function to build int16-prefixed binary data: stop point for empty
%% list.
%%
build_int_prefixed([], BinaryData) ->
    BinaryData;

%%
%% Inner function to build int16-prefixed binary data.
%%
build_int_prefixed([Head | RemainData], BinaryData) when is_list(Head)->
    LengthHead = length(Head),
    BinData = list_to_binary(Head),
    build_int_prefixed(RemainData, <<BinaryData/binary, LengthHead:16,
                       BinData/binary>>);

build_int_prefixed([IntHead | RemainData], BinaryData) when is_integer(IntHead)->
    build_int_prefixed([integer_to_list(IntHead) | RemainData], BinaryData);

build_int_prefixed([FloatHead | RemainData], BinaryData) when is_float(FloatHead) ->
    build_int_prefixed([float_to_list(FloatHead) | RemainData], BinaryData);

build_int_prefixed([true | RemainData], BinaryData) ->
    build_int_prefixed(["True" | RemainData], BinaryData);

build_int_prefixed([false | RemainData], BinaryData) ->
    build_int_prefixed(["False" | RemainData], BinaryData).


%%
%% Helper to get data from a socket.
%%
wait_reply(_, Timeout) ->
    receive
        {tcp, _, Reply} ->
            {value, Reply}
        after Timeout ->
            timeout
    end.


process_command(AmpClientPid, ArgList) ->
    case is_process_alive(AmpClientPid) of
        false ->
            {error, "Invalid process handle"};
        true ->
             AmpClientPid ! {command, self(), ArgList}
    end.


%%
%% Test function to call the AMP sum command.
%%
%% Example::
%%      amp:sum(Pid, 12, 34).
sum(AmpClientPid, A, B) ->
    case process_command(AmpClientPid, ["Sum",
                                        "a", A,
                                        "b", B]) of
        {error, Reason} ->
            {error, Reason};
        _ ->
            receive
                {value, Data} ->
                    case Data of
                        ["total", Answer] ->
                            list_to_integer(Answer)
                    end;
                {error, Data} ->
                    {error, Data}
            end
    end.


%%
%% Test function to call the AMP divide command.
%%
%% Example::
%%      amp:divide(Pid, 12, 4).
divide(AmpClientPid, A, B) ->
    case process_command(AmpClientPid, ["Divide",
                                        "numerator", A,
                                        "denominator", B]) of
        {error, Reason} ->
            {error, Reason};
        _ ->
        receive
            {value, Data} ->
                case Data of
                    ["result", Answer] ->
                        list_to_float(Answer)
                end;
            {error, Data} ->
                {error, Data}
        end
    end.

