plate fizzbuzzItem:
i:value >──[%15]──[?=0]──?──[const:FizzBuzz]──< out:value
                         │
                         [%3]──[?=0]──?──[const:Fizz]──< out:value
                                       │
                                       [%5]──[?=0]──?──[const:Buzz]──< out:value
                                                     │
                                                     [str]──< out:value
end

n:value >──[range]──[map:fizzbuzzItem]──< answer:stream
