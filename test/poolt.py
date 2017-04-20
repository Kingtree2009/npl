from multiprocessing import  Pool
import time


def sayHi(num):
    num += 1
    print "process %d start"% num
    time.sleep(10/num)
    print "process %d end"% num
    return num * num


p = Pool(processes=5)

result_list = []
for i in range(30):
    result_list.append(p.apply_async(sayHi, [i]))

# p.close()
# p.join()
id = 0
for res in result_list:
    print "wait %d" % id
    print res.get()
    id+=1